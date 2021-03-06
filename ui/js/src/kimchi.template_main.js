/*
 * Project Kimchi
 *
 * Copyright IBM, Corp. 2013
 *
 * Authors:
 *  Mei Na Zhou <zhmeina@cn.ibm.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *	 http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
kimchi.doListTemplates = function() {
    kimchi.listTemplates(function(result) {
        var titleValue = {
            'tempnum' : result.length
        };
        var titleTemp = $('#titleTmpl').html();
        var titleHtml = '';
        if (result.length) {
            titleHtml = kimchi.template(titleTemp, titleValue);
        } else {
            titleHtml = titleTemp.replace('{tempnum}', '0');
        }
        $('#templateTitle').html(titleHtml);
        var templateHtml = $('#templateTmpl').html();
        if (result && result.length) {
            var listHtml = '';
            $.each(result, function(index, value) {
                listHtml += kimchi.template(templateHtml, value);
            });
            $('#templateList').html(listHtml);
            kimchi.bindClick();
        } else {
            $('#templateList').html("");
        }
    }, function() {
        kimchi.message.error(i18n['kimchi.list.template.fail.msg']);
    });
};

kimchi.bindClick = function() {
    $('.template-edit').on('click', function(event) {
        var templateName = $(this).data('template');
        kimchi.selectedTemplate = templateName;
        kimchi.window.open("template-edit.html");
    });
    $('.template-delete').on('click', function(event) {
        var $template = $(this);
        var settings = {
            title : i18n['msg.confirm.delete.title'],
            content : i18n['msg.template.confirm.delete'],
            confirm : i18n['msg.confirm.delete.confirm'],
            cancel : i18n['msg.confirm.delete.cancel']
        };
        kimchi.confirm(settings, function() {
            var templateName = $template.data('template');
            kimchi.deleteTemplate(templateName, "", "");
            kimchi.doListTemplates();
        }, function() {
        });
    });
}
kimchi.hideTitle = function() {
    $('#tempTitle').hide();
};

kimchi.template_main = function() {
    $("#template-add").on("click", function(event) {
        kimchi.window.open('template-add.html');
    });
    kimchi.doListTemplates();
};
