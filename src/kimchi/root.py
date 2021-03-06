#
# Project Kimchi
#
# Copyright IBM, Corp. 2013
#
# Authors:
#  Anthony Liguori <aliguori@us.ibm.com>
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

import cherrypy
import template
import controller


def error_production_handler(status, message, traceback, version):
    data = {'code': status, 'reason': message}
    return template.render('error.html', data)

def error_development_handler(status, message, traceback, version):
    data = {'code': status, 'reason': message, 'call_stack': cherrypy._cperror.format_exc()}
    return template.render('error.html', data)


class Root(controller.Resource):
    _handled_error = ['error_page.400',
        'error_page.404', 'error_page.405',
        'error_page.406', 'error_page.415', 'error_page.500']
    def __init__(self, model, dev_env):
        if not dev_env:
            self._cp_config = dict([(key, error_production_handler) for key in self._handled_error])
        else:
            self._cp_config = dict([(key, error_development_handler) for key in self._handled_error])
        controller.Resource.__init__(self, model)
        self.vms = controller.VMs(model)
        self.templates = controller.Templates(model)
        self.storagepools = controller.StoragePools(model)
        self.tasks = controller.Tasks(model)

    def get(self):
        return self.default('kimchi-ui.html')

    @cherrypy.expose
    def default(self, page, **kwargs):
        if page.endswith('.html'):
            return template.render(page, None)
        raise cherrypy.HTTPError(404)
