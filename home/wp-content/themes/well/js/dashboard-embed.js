/*
 * The dashboard iframe on the Dashboard page (page-dashboard.php). The dashboard (/?embed=1) posts its content
 * height, and the iframe is set to it, so the dashboard scrolls with this page instead of inside a box of its own.
 * In return this page tells the dashboard which part of the iframe is in the window (on scroll and resize), so it
 * can open its dialogs there. Messages are only accepted from the iframe itself, at the dashboard's origin
 * (data-dashboard-origin), and only sent to that origin.
 *
 * Until the first height arrives (or if it never does, from an older dashboard) the iframe keeps the height the
 * page gives it, and the dashboard scrolls inside it as before.
 */
(function () {
    'use strict';

    var frame = document.getElementById('well-dashboard-frame');
    if (!frame || !window.postMessage) {
        return;
    }
    var box = frame.parentNode;
    frame.addEventListener('load', function () {
        box.classList.add('is-loaded');
    });

    var origin = frame.getAttribute('data-dashboard-origin');
    if (!origin) {
        return;
    }
    var HEIGHT = 'well-embed:height';
    var VIEWPORT = 'well-embed:viewport';
    var MAX_HEIGHT = 50000; // a guard against a runaway value, far above any real page
    var queued = false;

    // The part of the iframe in the window, in the iframe's own pixels: from `top` down, `height` tall.
    function sendViewport() {
        queued = false;
        if (!frame.contentWindow) {
            return;
        }
        var rect = frame.getBoundingClientRect();
        var top = Math.max(0, -rect.top);
        var bottom = Math.min(rect.height, window.innerHeight - rect.top);
        if (bottom <= top) {
            return; // out of view: the dashboard keeps the last part it was told
        }
        frame.contentWindow.postMessage({ type: VIEWPORT, top: top, height: bottom - top }, origin);
    }

    function queueViewport() {
        if (!queued) {
            queued = true;
            window.requestAnimationFrame(sendViewport);
        }
    }

    window.addEventListener('message', function (event) {
        if (event.origin !== origin || event.source !== frame.contentWindow) {
            return;
        }
        var data = event.data;
        if (!data || data.type !== HEIGHT || typeof data.height !== 'number') {
            return;
        }
        var height = Math.round(data.height);
        if (!(height > 0) || height > MAX_HEIGHT) {
            return;
        }
        box.classList.add('is-loaded');
        if (frame.style.height !== height + 'px') {
            frame.style.height = height + 'px';
            queueViewport(); // the part in view has changed
        }
    });

    window.addEventListener('scroll', queueViewport, { passive: true });
    window.addEventListener('resize', queueViewport);
    // The dashboard answers the first of these with its height, so a height it sent before this script ran isn't lost
    frame.addEventListener('load', queueViewport);
    queueViewport();
})();
