/*
 * Project Kimchi
 *
 * Copyright IBM, Corp. 2013
 *
 * Authors:
 *  Hongliang Wang <hlwanghl@cn.ibm.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
kimchi.message = function(msg, level) {
    if ($('#messageField').size() < 1) {
        $(document.body).append('<div id="messageField"></div>');
    }
    var message = '<div class="message ' + (level || '') + '" style="display: none;">';
    message += '<div class="close">X</div>';
    message += '<div class="content">' + msg + '</div>';
    message += '</div>';
    var $message = $(message);
    $('#messageField').append($message);
    $message.fadeIn(100);

    setTimeout(function() {
        $message.fadeOut(2000, function() {
            $(this).remove();
        });
    }, 2000);

    $('#messageField').on("click", ".close", function(e) {
        $(this).parent().fadeOut(200, function() {
            $(this).remove();
        });
    });
};

/**
 * A public function of confirm box.
 * @param msg  type:[object]
 * @param msg.title The title of the confirm box.
 * @param msg.content The main text of the confirm box.
 * @param msg.confirm The text of the confirm button.
 * @param msg.cancel the text of the cancel button.
 * @param confirmCallback the callback function of click the confirm button.
 * @param cancelCallback The callback function of click the cancel and X button.
 */
kimchi.confirm = function(settings, confirmCallback, cancelCallback) {
    if ($('#confirmbox-container ').size() < 1) {
        $(document.body).append('<div id="confirmbox-container" class="bgmask"></div>');
    }
    var confirmboxHtml = '<div class="confirmbox">';
    confirmboxHtml += '<header>';
    confirmboxHtml += '<h4 class="title">' + settings.title + '</h4>';
    confirmboxHtml += '<div class="close cancel">X</div>';
    confirmboxHtml += '</header>';
    confirmboxHtml += '<div class="content">';
    confirmboxHtml += settings.content + '</div>';
    confirmboxHtml += '<footer>';
    confirmboxHtml += '<div class="btn-group">';
    confirmboxHtml += '<button id="button-confirm" class="btn-small"><span class="text">'
        + settings.confirm + '</span></button>';
    confirmboxHtml += '<button id="button-cancel" class="btn-small cancel"><span class="text">'
        + settings.cancel + '</span></button>';
    confirmboxHtml += '</div>';
    confirmboxHtml += '</footer>';
    confirmboxHtml += '</div>';
    var confirmboxNode = $(confirmboxHtml);
    $('#confirmbox-container').append(confirmboxNode);
    confirmboxNode.fadeIn();

    $('#confirmbox-container').on("click", "#button-confirm", function(e) {
        confirmCallback();
        confirmboxNode.fadeOut(1, function() {
            $('#confirmbox-container').remove();
        });
    });
    $('#confirmbox-container').on("click", ".cancel", function(e) {
        cancelCallback();
        confirmboxNode.fadeOut(1, function() {
            $('#confirmbox-container').remove();
        });
    });
};

kimchi.message.warn = function(msg) {
    kimchi.message(msg, 'warn');
};
kimchi.message.error = function(msg) {
    kimchi.message(msg, 'error');
};
kimchi.message.success = function(msg) {
    kimchi.message(msg, 'success');
};
