#
# Kimchi
#
# Copyright IBM Corp, 2013
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

SOURCE = \
	asynctask.py      \
	auth.py           \
	config.py         \
	controller.py     \
	exception.py      \
	__init__.py       \
	isoinfo.py        \
	mockmodel.py      \
	model.py          \
	objectstore.py    \
	osinfo.py         \
	root.py           \
	screenshot.py     \
	server.py         \
	template.py       \
	vmtemplate.py     \
	vnc.py            \
	websocket.py      \
	websockify.py     \
	xmlutils.py

EXTRA_DIST = config.py.in

kimchi_PYTHON = $(SOURCE)

kimchidir = $(pythondir)/kimchi

do_substitution = \
	sed -e 's,[@]prefix[@],$(prefix),g'             \
	-e 's,[@]sysconfdir[@],$(sysconfdir),g'         \
	-e 's,[@]localstatedir[@],$(localstatedir),g'   \
	-e 's,[@]pkgdatadir[@],$(pkgdatadir),g'


config.py: config.py.in Makefile
	$(do_substitution) < $(srcdir)/config.py.in > config.py

BUILT_SOURCES = config.py
CLEANFILES = config.py
