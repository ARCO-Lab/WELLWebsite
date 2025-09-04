/* This code was adapted from MacSites' WordPress Theme */

(function () {
    // Initialize the count down date to last day of the year
    const countdownTimerCountdown = document.querySelector(".countdown-timer__countdown");

    // if countdownTimerCountdown is null, then the countdown timer is not present on the page
    if (countdownTimerCountdown === null) {
        return;
    }

    // Get the countdown date from the data-countdown attribute. If the date is invalid,
    // log an error and return.
    const countDownDate = new Date(countdownTimerCountdown.dataset.countdown).getTime();
    if (isNaN(countDownDate)) {
        console.error('Invalid countdown date');
        return;
    }

    // Get the countdown element
    const countdown = document.querySelector("#countdown");
    // Set up constants used for calculating the time remaining
    const numMillisecondsInDay = 1000 * 60 * 60 * 24;
    const numMillisecondsInHour = 1000 * 60 * 60;
    const numMillisecondsInMinute = 1000 * 60;
    const numMillisecondsInSecond = 1000;

    //  Add event listener to the window object
    window.addEventListener("load", function () {

        const countdownfunction = setInterval(function () {

            const now = new Date().getTime();
            const timeRemaining = countDownDate - now;

            if (timeRemaining <= 0) {
                clearInterval(countdownfunction);
                countdown.textContent = "E-C-L-I-P-S-E 🌘";
            } else {
                const days = Math.floor(timeRemaining / numMillisecondsInDay);
                const hours = Math.floor((timeRemaining % numMillisecondsInDay) / numMillisecondsInHour);
                const minutes = Math.floor((timeRemaining % numMillisecondsInHour) / numMillisecondsInMinute);
                const seconds = Math.floor((timeRemaining % numMillisecondsInMinute) / numMillisecondsInSecond);

                // Set labels according to scrren size
                setLabels();

                // Display the result for individual units of time
                countdown.querySelector("#days").textContent = days;
                countdown.querySelector("#hours").textContent = String(hours).padStart(2, '0');
                countdown.querySelector("#minutes").textContent = String(minutes).padStart(2, '0');
                countdown.querySelector("#seconds").textContent = String(seconds).padStart(2, '0');
            }
        }, 1000); // 1000 milliseconds = 1 second

    }, false);
})();


/**
 * Returns the current breakpoint based on the window width.
 * @returns {string} The current breakpoint ('xs', 'sm', 'md', 'lg', 'xl').
 */
function getBreakpoint() {
    const width = window.innerWidth;

    if (width < 576) {
        return 'xs';
    } else if (width < 768) {
        return 'sm';
    } else if (width < 992) {
        return 'md';
    } else if (width < 1200) {
        return 'lg';
    } else {
        return 'xl';
    }
}

/**
 * Sets the labels for the countdown timer based on the current breakpoint.
 * @returns {void}
 * @see getBreakpoint
*/
function setLabels() {
    const countdown = document.querySelector("#countdown");
    const breakpoint = getBreakpoint();

    const timeUnits = {
        'days': 'Days',
        'hours': 'Hours',
        'minutes': 'Minutes',
        'seconds': 'Seconds'
    };

    const shortTimeUnits = {
        'days': 'D',
        'hours': 'H',
        'minutes': 'M',
        'seconds': 'S'
    };

    const units = breakpoint === 'xs' || breakpoint === 'sm' ? shortTimeUnits : timeUnits;

    Object.keys(units).forEach(unit => {
        const element = countdown.querySelector(`#${unit}`);
        element.nextElementSibling.textContent = units[unit];
    });
}
