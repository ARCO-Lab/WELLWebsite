/**
 * Comm100 Live Chat Wrapper
 * This file is used to add skip link to the chat window
 * and set focus to the chat window when it is restored.
 *
 * @package Macsites_Theme
 * @since 1.0.0
 * @version 1.0.0
 * @license GPL-2.0-or-later
 * @link https://macsites.mcmaster.ca/
 * @link https://www.comm100.com/
 * @note This script is loaded via the header-footer script plugin in your WordPress dashboard.
 */


// Add IIFE to avoid polluting global namespace
(function () {
    window.addEventListener('load', function (event) {
        setTimeout(function () {
            // Get the chat window element
            const comm100Btn = document.querySelector('[id^="comm100-float-button"]');
            // Check if the chat window element and Comm100API object are available
            if (!comm100Btn || !Comm100API) {
                return;
            }
            // Check if the chat window is visible
            if (comm100Btn.offsetParent) {
                const btnId = comm100Btn.id;
                // Insert the 'skip to chat link' before the 'skip to content link'
                // Set the href attribute to the button id of the chat window (comm100Btn.id)
                // Add an id to the skip link
                document.querySelector('#skiptocontent').insertAdjacentHTML(
                    'afterbegin',
                    '<a href="#' + btnId + '" id="skiptochat">Skip to Live Chat Support</a>'
                );
                // Add event listener to the newly inserted skip link
                document.querySelector('#skiptochat').addEventListener('click', function (e) {
                    // Prevent default behaviour
                    e.preventDefault();
                    // Activate the chat window if the chat window is minimized
                    if (Comm100API) {
                        Comm100API.open_chat_window();
                    }
                });
            }
            // Set focus to the chat window when it is restored
            function reFocus() {
                let iframe = document.getElementById("chat_window_container");
                let minimize = iframe?.contentWindow.document.querySelector(".window__operation > button");
                minimize.focus();
            }
            // Get the Comm100API object and add an event listener for the
            // livechat.prechat.restore custom event
            Comm100API.on('livechat.prechat.restore', function () {
                // Set time out and call reFocus function after 200ms
                setTimeout(() => {
                    reFocus();
                  }, 200);
            });
            // Get the Comm100API object and add an event listener for the
            // live chat.chat.restore custom event
            Comm100API.on('livechat.chat.restore', function () {
                // Set time out and call reFocus function after 200ms
                setTimeout(() => {
                    reFocus();
                  }, 200);
            });
            // Get the Comm100API object and add an event listener for the
            // livechat.postChat.restore custom event
            Comm100API.on('livechat.postChat.restore', function () {
                // Set time out and call reFocus function after 200ms
                // setTimeout(reFocus, 200);
                setTimeout(() => {
                    reFocus();
                  }, 200);
            });
            // Get the Comm100API object and add an event listener for the
            // livechat.offlineMessage.restore custom event
            Comm100API.on('livechat.offlineMessage.restore', function () {
                // Set time out and call reFocus function after 200ms
                setTimeout(() => {
                    reFocus();
                  }, 200);
            });
        }, 1000);
    });
})();
