/* This code was adapted from MacSites' WordPress Theme */

/**
 * This file is used to fix the accessibility issue with the WP Forms name field.
 * The issue is that the name field is a single field and the label is not
 * associated with the input field.
 */

const setup_wp_form_a11y_fix_name_field = () => {
    // Get the form
    const form = document.querySelector('.wpforms-form');
    // Get the form component
    try {
        if (form) {
            const nameFields = {
                first: form.querySelector('.wpforms-field-name-first'),
                last: form.querySelector('.wpforms-field-name-last'),
                name: form.querySelector('.wpforms-field-name')
            };
            // Check if the name field is a single field
            if (nameFields.name) {
                // Get the label
                const label1 = nameFields.name.querySelector('label');
                if (nameFields.first || nameFields.last) {
                    // Replace the label with a span element
                    const spanEl = document.createElement('span');
                    const parent = label1.parentElement;
                    // Create a span element and add the label text
                    spanEl.innerHTML = label1.innerHTML;
                    // Add the label class to the span element
                    spanEl.classList.add(label1.classList[0]);
                    // Add the span element to the parent element as the first child
                    parent.insertBefore(spanEl, parent.firstChild);
                    // Remove the label element
                    label1.remove();
                    // Notify the console
                    console.log('WP Form A11y Fix: Name field label replaced with span element.');
                }
            }
        }
    } catch (error) {
        console.error(error);
    }
}

// IIFE
(() => {
    // Setup the mute components for WP Forms and ACF WYSIWYG
    window.addEventListener('load', () => {
        setup_wp_form_a11y_fix_name_field();
    });
})();