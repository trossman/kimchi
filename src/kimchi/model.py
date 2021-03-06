#
# Project Kimchi
#
# Copyright IBM, Corp. 2013
#
# Authors:
#  Adam Litke <agl@linux.vnet.ibm.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import re
import threading
import time
import libvirt
import functools
import os
import json
import copy
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import vmtemplate
import config
import xmlutils
import vnc
from screenshot import VMScreenshot
from kimchi.objectstore import ObjectStore
from kimchi.asynctask import AsyncTask
from kimchi.exception import *


def _uri_to_name(collection, uri):
    expr = '/%s/(.*?)/?$' % collection
    m = re.match(expr, uri)
    if not m:
        raise InvalidParameter(uri)
    return m.group(1)

def template_name_from_uri(uri):
    return _uri_to_name('templates', uri)

def pool_name_from_uri(uri):
    return _uri_to_name('storagepools', uri)

def get_vm_name(vm_name, t_name, name_list):
    if vm_name:
        return vm_name
    for i in xrange(1, 1000):
        vm_name = "%s-vm-%i" % (t_name, i)
        if vm_name not in name_list:
            return vm_name
    raise OperationFailed("Unable to choose a VM name")

class Model(object):
    dom_state_map = {0: 'nostate',
                     1: 'running',
                     2: 'blocked',
                     3: 'paused',
                     4: 'shutdown',
                     5: 'shutoff',
                     6: 'crashed'}

    pool_state_map = {0: 'inactive',
                      1: 'initializing',
                      2: 'active',
                      3: 'degraded',
                      4: 'inaccessible'}

    volume_type_map = {0: 'file',
                       1: 'block',
                       2: 'directory',
                       3: 'network'}

    def __init__(self, libvirt_uri=None, objstore_loc=None):
        self.libvirt_uri = libvirt_uri or 'qemu:///system'
        self.conn = LibvirtConnection(self.libvirt_uri)
        self.objstore = ObjectStore(objstore_loc)
        self.graphics_ports = {}
        self.cpu_stats = {}
        self.next_taskid = 1

    def _get_cpu_stats(self, name, info):
        timestamp = time.time()
        prevCpuTime = 0
        prevTimestamp = 0

        prevStats = self.cpu_stats.get(name, None)
        if prevStats is not None:
            prevTimestamp = prevStats["timestamp"]
            prevCpuTime = prevStats["cputime"]

        self.cpu_stats[name] = {'timestamp': timestamp, 'cputime': info[4]}

        cpus = info[3]
        cpuTime = info[4] - prevCpuTime
        base = (((cpuTime) * 100.0) / ((timestamp - prevTimestamp) * 1000.0 * 1000.0 * 1000.0))

        return max(0.0, min(100.0, base / cpus))

    def vm_lookup(self, name):
        dom = self._get_vm(name)
        info = dom.info()
        state = Model.dom_state_map[info[0]]
        screenshot = None
        cpu_stats = 0
        graphics_type, _ = self._vm_get_graphics(name)
        # 'port' must remain None until a connect call is issued
        graphics_port = (self.graphics_ports.get(name, None) if state == 'running'
                      else None)
        try:
            if state == 'running':
                screenshot = self.vmscreenshot_lookup(name)
                cpu_stats = self._get_cpu_stats(name, info)
        except NotFoundError:
            pass

        with self.objstore as session:
            try:
                extra_info = session.get('vm', name)
            except NotFoundError:
                extra_info = {}
        icon = extra_info.get('icon')

        return {'state': state,
                'cpu_stats': str(cpu_stats),
                'memory': info[2] >> 10,
                'screenshot': screenshot,
                'icon': icon,
                'graphics': {"type": graphics_type, "port": graphics_port}}

    def _vm_get_disk_paths(self, dom):
        xml = dom.XMLDesc(0)
        xpath = "/domain/devices/disk[@device='disk']/source/@file"
        return xmlutils.xpath_get_text(xml, xpath)

    def vm_delete(self, name):
        if self._vm_exists(name):
            self._vmscreenshot_delete(name)
            conn = self.conn.get()
            dom = self._get_vm(name)
            paths = self._vm_get_disk_paths(dom)
            info = self.vm_lookup(name)

            if info['state'] == 'running':
                self.vm_stop(name)

            dom.undefine()

            for path in paths:
                vol = conn.storageVolLookupByPath(path)
                vol.delete(0)

            with self.objstore as session:
                session.delete('vm', name, ignore_missing=True)

    def vm_start(self, name):
        dom = self._get_vm(name)
        dom.create()

    def vm_stop(self, name):
        if self._vm_exists(name):
            dom = self._get_vm(name)
            dom.destroy()

    def _vm_get_graphics(self, name):
        dom = self._get_vm(name)
        xml = dom.XMLDesc(0)
        expr = "/domain/devices/graphics/@type"
        res = xmlutils.xpath_get_text(xml, expr)
        graphics_type = res[0] if res else None
        port = None
        if graphics_type:
            expr = "/domain/devices/graphics[@type='%s']/@port" % graphics_type
            res = xmlutils.xpath_get_text(xml, expr)
            port = int(res[0]) if res else None
        # FIX ME
        # graphics_type should be 'vnc' or None.  'spice' should only be
        # returned if we support it in the future.
        graphics_type = None if graphics_type != "vnc" else graphics_type
        return graphics_type, port

    def vm_connect(self, name):
        graphics, port = self._vm_get_graphics(name)
        if graphics == "vnc" and port != None:
            port = vnc.new_ws_proxy(port)
            self.graphics_ports[name] = port
        else:
            raise OperationFailed("Unable to find VNC port in %s" % name)

    def vms_create(self, params):
        try:
            t_name = template_name_from_uri(params['template'])
        except KeyError, item:
            raise MissingParameter(item)

        vm_list = self.vms_get_list()
        name = get_vm_name(params.get('name'), t_name, vm_list)
        # incoming text, from js json, is unicode, do not need decode
        if name in vm_list:
            raise InvalidOperation("VM already exists")
        t = self._get_template(t_name)

        conn = self.conn.get()
        pool_uri = params.get('storagepool', t.info['storagepool'])
        pool_name = pool_name_from_uri(pool_uri)
        pool = conn.storagePoolLookupByName(pool_name)
        xml = pool.XMLDesc(0)
        storage_path = xmlutils.xpath_get_text(xml, "/pool/target/path")[0]

        # Provision storage:
        # TODO: Rebase on the storage API once upstream
        vol_list = t.to_volume_list(name, storage_path)
        for v in vol_list:
            # outgoing text to libvirt, encode('utf-8')
            pool.createXML(v['xml'].encode('utf-8'), 0)

        # Store the icon for displaying later
        icon = t.info.get('icon')
        if icon:
            with self.objstore as session:
                session.store('vm', name, {'icon': icon})

        xml = t.to_vm_xml(name, storage_path)
        # outgoing text to libvirt, encode('utf-8')
        dom = conn.defineXML(xml.encode('utf-8'))
        return name

    def vms_get_list(self):
        conn = self.conn.get()
        ids = conn.listDomainsID()
        names = map(lambda x: conn.lookupByID(x).name(), ids)
        names += conn.listDefinedDomains()
        names = map(lambda x: x.decode('utf-8'), names)
        return sorted(names, key=unicode.lower)

    def vmscreenshot_lookup(self, name):
        dom = self._get_vm(name)
        d_info = dom.info()
        if Model.dom_state_map[d_info[0]] != 'running':
            raise NotFoundError('No screenshot for stopped vm')

        screenshot = self._get_screenshot(name)
        img_path = screenshot.lookup()
        # screenshot info changed after scratch generation
        with self.objstore as session:
            session.store('screenshot', name, screenshot.info)
        return img_path

    def _vmscreenshot_delete(self, name):
        screenshot = self._get_screenshot(name)
        screenshot.delete()
        with self.objstore as session:
            session.delete('screenshot', name)

    def template_lookup(self, name):
        t = self._get_template(name)
        return t.info

    def template_delete(self, name):
        with self.objstore as session:
            session.delete('template', name)

    def templates_create(self, params):
        name = params['name']
        with self.objstore as session:
            if name in session.get_list('template'):
                raise InvalidOperation("Template already exists")
            t = vmtemplate.VMTemplate(params, scan=True)
            session.store('template', name, t.info)
        return name

    def template_update(self, name, params):
        old_t = self.template_lookup(name)
        new_t = copy.copy(old_t)
        new_t.update(params)
        ident = name

        self.template_delete(name)
        try:
            ident = self.templates_create(new_t)
        except:
            ident = self.templates_create(old_t)
            raise
        return ident

    def templates_get_list(self):
        with self.objstore as session:
            return session.get_list('template')

    def add_task(self, target_uri, fn, opaque=None):
        id = self.next_taskid
        self.next_taskid = self.next_taskid + 1

        task = AsyncTask(id, target_uri, fn, self.objstore, opaque)

        return id

    def tasks_get_list(self):
        with self.objstore as session:
            return session.get_list('task')

    def task_lookup(self, id):
        with self.objstore as session:
            return session.get('task', str(id))

    def _vm_exists(self, name):
        try:
            self._get_vm(name)
            return True
        except NotFoundError:
            return False
        except:
            raise


    def _get_vm(self, name):
        conn = self.conn.get()
        try:
            # outgoing text to libvirt, encode('utf-8')
            return conn.lookupByName(name.encode("utf-8"))
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                raise NotFoundError("Virtual Machine '%s' not found" % name)
            else:
                raise

    def _get_template(self, name):
        with self.objstore as session:
            params = session.get('template', name)
        return vmtemplate.VMTemplate(params)

    def storagepools_create(self, params):
        conn = self.conn.get()
        try:
            xml = _get_pool_xml(**params)
            name = params['name']
        except KeyError, key:
            raise MissingParameter(key)
        pool = conn.storagePoolDefineXML(xml, 0)
        return name

    def storagepool_lookup(self, name):
        pool = self._get_storagepool(name)
        info = pool.info()
        xml = pool.XMLDesc(0)
        path = xmlutils.xpath_get_text(xml, "/pool/target/path")[0]
        pool_type = xmlutils.xpath_get_text(xml, "/pool/@type")[0]
        return {'state': Model.pool_state_map[info[0]],
                'path': path,
                'type': pool_type,
                'capacity': info[1] >> 20,
                'allocated': info[2] >> 20,
                'available': info[3] >> 20}

    def storagepool_activate(self, name):
        pool = self._get_storagepool(name)
        pool.create(0)

    def storagepool_deactivate(self, name):
        pool = self._get_storagepool(name)
        pool.destroy()

    def storagepool_delete(self, name):
        pool = self._get_storagepool(name)
        if pool.isActive():
            raise InvalidOperation(
                        "Unable to delete the active storagepool %s" % name)
        pool.undefine()

    def storagepools_get_list(self):
        conn = self.conn.get()
        names = conn.listStoragePools()
        names += conn.listDefinedStoragePools()
        return names

    def _get_storagepool(self, name):
        conn = self.conn.get()
        try:
            return conn.storagePoolLookupByName(name)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_STORAGE_POOL:
                raise NotFoundError("Storage Pool '%s' not found" % name)
            else:
                raise

    def storagevolumes_create(self, pool, params):
        info = self.storagepool_lookup(pool)
        try:
            name = params['name']
            xml = _get_volume_xml(**params)
        except KeyError, key:
            raise MissingParameter(key)
        pool = self._get_storagepool(pool)
        pool.createXML(xml, 0)
        return name

    def storagevolume_lookup(self, pool, name):
        vol = self._get_storagevolume(pool, name)
        path = vol.path()
        info = vol.info()
        xml = vol.XMLDesc(0)
        fmt = xmlutils.xpath_get_text(xml, "/volume/target/format/@type")[0]
        return {'type': Model.volume_type_map[info[0]],
                'capacity': info[1] >> 20,
                'allocation': info[2] >> 20,
                'path': path,
                'format': fmt}

    def storagevolume_wipe(self, pool, name):
        volume = self._get_storagevolume(pool, name)
        volume.wipePattern(libvirt.VIR_STORAGE_VOL_WIPE_ALG_ZERO, 0)

    def storagevolume_delete(self, pool, name):
        volume = self._get_storagevolume(pool, name)
        volume.delete(0)

    def storagevolume_resize(self, pool, name, size):
        size = size << 20
        volume = self._get_storagevolume(pool, name)
        volume.resize(size, 0)

    def storagevolumes_get_list(self, pool):
        pool = self._get_storagepool(pool)
        return pool.listVolumes()

    def _get_storagevolume(self, pool, name):
        pool = self._get_storagepool(pool)
        try:
            return pool.storageVolLookupByName(name)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_STORAGE_VOL:
                raise NotFoundError("Storage Volume '%s' not found" % name)
            else:
                raise

    def _get_screenshot(self, name):
        with self.objstore as session:
            try:
                params = session.get('screenshot', name)
            except NotFoundError:
                params = {'name': name}
                session.store('screenshot', name, params)
        return LibvirtVMScreenshot(params, self.conn)


class LibvirtVMScreenshot(VMScreenshot):
    def __init__(self, vm_name, conn):
        VMScreenshot.__init__(self, vm_name)
        self.conn = conn

    def _generate_scratch(self, thumbnail):
        def handler(stream, buf, opaque):
            fd = opaque
            os.write(fd, buf)

        fd = os.open(thumbnail, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, 0644)
        try:
            conn = self.conn.get()
            # outgoing text to libvirt, encode('utf-8')
            dom = conn.lookupByName(self.vm_name.encode('utf-8'))
            stream = conn.newStream(0)
            mimetype = dom.screenshot(stream, 0, 0)
            stream.recvAll(handler, fd)
        except libvirt.libvirtError:
            try:
                stream.abort()
            except:
                pass
            raise NotFoundError("Screenshot not supported for %s" %
                                self.vm_name)
        else:
            stream.finish()
        finally:
            os.close(fd)


def _get_pool_xml(**kwargs):
    # Required parameters
    # name:
    # type:
    # path:
    xml = """
    <pool type='%(type)s'>
      <name>%(name)s</name>
      <target>
        <path>%(path)s</path>
      </target>
    </pool>
    """ % kwargs
    return xml


def _get_volume_xml(**kwargs):
    # Required parameters
    # name:
    # capacity:
    #
    # Optional:
    # allocation:
    # format:
    kwargs.setdefault('allocation', 0)
    kwargs.setdefault('format', 'qcow2')

    xml = """
    <volume>
      <name>%(name)s</name>
      <allocation unit="MiB">%(allocation)s</allocation>
      <capacity unit="MiB">%(capacity)s</capacity>
      <source>
      </source>
      <target>
        <format type='%(format)s'/>
      </target>
    </volume>
    """ % kwargs
    return xml


class LibvirtConnection(object):
    def __init__(self, uri):
        self.uri = uri
        self._connections = {}
        self._connectionLock = threading.Lock()

    def get(self, conn_id=0):
        """
        Return current connection to libvirt or open a new one.
        """

        with self._connectionLock:
            conn = self._connections.get(conn_id)
            if not conn:
                # TODO: Retry
                conn = libvirt.open(self.uri)
                self._connections[conn_id] = conn
                # In case we're running into troubles with keeping the connections
                # alive we should place here:
                # conn.setKeepAlive(interval=5, count=3)
                # However the values need to be considered wisely to not affect
                # hosts which are hosting a lot of virtual machines
            return conn
