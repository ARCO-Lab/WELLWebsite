/* This code was adapted from MacSites' WordPress Theme */

/* This code was adapted from MacSites' WordPress Theme */

/**
 *
 * @returns string selectId- The selector string
 */
var getSelector = function () {
  let selectId = '';

  // Get the post type from the form
  const postType = document.querySelector('input[name=post_type]')?.value ?? '';
  // Assign correct selector type for the post type
  selectId = postType;
  selectId = postType === 'resources' ? 'resource-types' : selectId;
  selectId = postType === 'people' ? 'people-types' : selectId;
  selectId = postType === 'post' ? 'categories' : selectId;
  selectId = postType === 'event' ? 'event-categories' : selectId;
  selectId = postType === 'testimonial' ? 'testimonial-type' : selectId;
  // Build selector query string
  selectId = `select[id^="${selectId}"]`;

  return selectId;
}

/**
 * Return various media query matches
 *
 * @returns Object mediaQuery - The media query matches
 */
var mediaQueries = function () {
  const matchMediaQuery = (window.matchMedia || window.msMatchMedia);
  // Return various media query matches
  return {
    isMobile: matchMediaQuery('(max-width: 767px)').matches,
    isTablet: matchMediaQuery('(min-width: 768px) and (max-width: 1023px)').matches,
    isDesktop: matchMediaQuery('(min-width: 1024px)').matches,
    isLargeDesktop: matchMediaQuery('(min-width: 1440px)').matches,
    isExtraLargeDesktop: matchMediaQuery('(min-width: 1920px)').matches,
  }
}

/**
 *
 * @param Object dataElementRow - The row element
 * @returns
 */
var loadFilteredPosts = function (dataElementRow) {

  return new Promise((resolve, reject) => {
    const scrollTarget = document.querySelector('.scroll-target');
    const postType = jQuery("input[name=post_type]").val();
    const formData = jQuery('form#form__filter').serializeArray();
    const ajax_url = form_process.ajax_url;
    const maxPages = document.querySelector('[data-max-num-pages]').dataset?.maxNumPages;
    // Set the max number of pages to the scrollTarget element
    scrollTarget.dataset.maxPages = maxPages;

    // Set various values for the form data
    formData.forEach((item) => {
      if (item.name === 'paged') {
        item.value = scrollTarget.dataset.page;
      }
      if (item.name === 'template') {
        if (item.value.includes('resources')) {
          item.value = item.value.replace('loop-resources', 'loop-resources-partial');
        } else if (item.value.includes('people')) {
          item.value = item.value.replace('loop-people', 'loop-people-partial');
        }
      }
    });
    // Use an async function to fetch the posts
    const fetchPosts = async () => {
      // Call the async function
      const loader = document.querySelector('.loader');
      loader ? loader.style.display = 'block' : null;
      // Use await to get the data
      await jQuery.ajax({
        type: 'POST',
        url: ajax_url,
        data: formData,
        success: (data) => {
          // console.log(data);
          if (postType === 'event') {
            jQuery('#filterData').empty().append(data);
          } else {
            jQuery(dataElementRow).append(data);
          }
          if (data.length == 0) {
            // remove 'searchApplied' flag from session storage
            if (sessionStorage.getItem('searchApplied')) {
              sessionStorage.removeItem('searchApplied');
            }
            // remove 'filterApplied' flag from session storage
            if (sessionStorage.getItem('filterApplied')) {
              sessionStorage.removeItem('filterApplied');
            }
          }
          // Resolve the promise
          resolve(data.length);
        },
        error: () => {
          // Reject the promise
          reject('No posts found');
        }
      })
    }
    // Call the fetchPosts function
    fetchPosts().then(() => {
      // Hider the loading spinner
      const loader = document.querySelector('.loader');
      loader ? loader.style.display = 'none' : null;
    }).catch((error) => {
      console.error(error);
    })
  });
}

jQuery(document).ready(function ($) {

  $('#left-nav li.current_page_ancestor div.collapse').addClass('show');

  if (0 < $('table.table.table-striped').length) {
    $('table.table.table-striped').wrap('<div class="table-responsive"></div>');
  }

  // Diable autocomplete for form fields
  const inputForms = Array.from(document.querySelectorAll('.wpforms-form'));
  const inputEls = Array.from(document.querySelectorAll('.wpforms-form input'));

  if (inputForms) {
    inputForms.forEach(el => {
      if (!el.getAttribute('autocomplete')) {
        el.setAttribute('autocomplete', 'off');
      }
    });
  }

  if (inputEls) {
    inputEls.forEach(el => {
      if (!el.getAttribute('autocomplete')) {
        el.setAttribute('autocomplete', 'new-password');
      }
    });
  }

  let formEl = document.querySelector('[name="posts_per_page"]');
  // Check if settings is defined
  if (typeof settings !== 'undefined') {
    formEl.value = settings.posts_per_page;
  }

  // Setup the debounce function for the search input
  const debounce = (fn, timeout = 200) => {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => { fn.apply(this, args); }, timeout);
    };
  }

  const searchText = () => {
    // console.log(document.querySelector("input#search-input").value);
    let postType = $("input[name=post_type]").val();
    let formData = $('form#form__filter').serializeArray();
    let ajax_url = form_process.ajax_url;
    // console.log(formData, postType);
    $.ajax({
      type: 'POST',
      url: ajax_url,
      data: formData,
      success: (data) => {
        if (postType === 'event') {
          $('#filterData').empty().append(data);
        } else {
          $('main#site-content').empty().append(data);
          // Get the page number from the scrolltarget element
          const pageNumber = document.querySelector('#scrolltarget')?.dataset?.page ?? 1;
          if (pageNumber == 1) {
            // Set a flag in session storage to indicate that search or filter has been applied
            sessionStorage.setItem('searchApplied', 'true');
            // Initialize the intersection observer
            initIntersectionObserver();
          }
        }
      },
      error: () => {
        console.log('no posts found');
      }
    });
  }

  const procesInput = debounce(() => searchText(), 300);

  $('input#search-input').on('keyup', function (e) {
    procesInput();
  });

  $('form#form__filter select').on('change', function (e) {
    //  $('form#form__filter').on('submit',function(e) {
    e.preventDefault();
    e.stopImmediatePropagation();

    let postType = $("input[name=post_type]").val();
    let formData = $('form#form__filter').serialize(),
      ajax_url = form_process.ajax_url;
    // console.log(formData);
    $.ajax({
      type: 'POST',
      url: ajax_url,
      data: formData,
      beforeSend: function () {
        //FadeOut
        // var children = $('#category-post-content').children();
        // children.fadeOut('slow');

        let selectId = getSelector();

        const els = Array.from(document.querySelectorAll(selectId));
        let urlComps = [], glue = '', newUrl = window.location.origin + window.location.pathname;

        els.forEach((el, idx) => {
          if (el.value !== '-1') {
            urlComps.push(`${el.id}=` + encodeURIComponent(el.value));
          }
        });

        if (urlComps.length > 1) {
          glue = '&';
        }

        if (urlComps.length > 0) {
          newUrl = `?${urlComps.join(glue)}`;
        }

        window.history.pushState({}, '', newUrl);
      },
      success: function (data) {
        //Fade in new content
        // console.log(data);
        if (postType === 'event') {
          $('#filterData').empty().append(data);
        } else {
          $('main#site-content').empty().append(data);
          const pageNumber = document.querySelector('#scrolltarget')?.dataset?.page ?? 1;
          if (pageNumber == 1) {
            // Set a flag in session storage to indicate that search or filter has been applied
            sessionStorage.setItem('filterApplied', 'true');
            // Initialize the intersection observer
            initIntersectionObserver();
          }
        }
      },
      error: function () {
        console.log('no posts found');
      }
    });
    return false;
  });
  $('#form__filter').on('submit', function (e) {
    e.preventDefault();
    e.stopImmediatePropagation();

    let postType = $("input[name=post_type]").val();
    let formData = $('form#form__filter').serialize(),
      ajax_url = form_process.ajax_url;
    // console.log( formData );
    $.ajax({
      type: 'POST',
      url: ajax_url,
      data: formData,
      beforeSend: function () {
        //FadeOut
        // var children = $('#category-post-content').children();
        // children.fadeOut('slow');
      },
      success: function (data) {
        //Fade in new content
        // console.log(data);
        if (postType === 'event') {
          $('#filterData').empty().append(data);
        } else {
          $('main#site-content').empty().append(data);
        }
      },
      error: function () {
        console.log('no posts found');
      }
    });
    return false;
  });

  // News date filter - date from (will need to do date to)
  $('#news_filter_date-from').on('change', function (e) {
    //  $('form#form__filter').on('submit',function(e) {
    e.preventDefault();
    e.stopImmediatePropagation();

    let postType = $("input[name=post_type]").val();
    let formData = $('form#form__filter').serialize(),
      ajax_url = form_process.ajax_url;
    // console.log( formData );
    $.ajax({
      type: 'POST',
      url: ajax_url,
      data: formData,
      beforeSend: function () {
        //FadeOut
        // var children = $('#category-post-content').children();
        // children.fadeOut('slow');
      },
      success: function (data) {
        //Fade in new content
        // console.log(data);
        if (postType === 'event') {
          $('#filterData').empty().append(data);
        } else {
          $('main#site-content').empty().append(data);
        }
      },
      error: function () {
        console.log('no posts found');
      }
    });
    return false;
  });

  $('#news_filter_date-to').on('change', function (e) {
    //  $('form#form__filter').on('submit',function(e) {
    e.preventDefault();
    e.stopImmediatePropagation();

    let postType = $("input[name=post_type]").val();
    let formData = $('form#form__filter').serialize(),
      ajax_url = form_process.ajax_url;
    // console.log(formData);
    $.ajax({
      type: 'POST',
      url: ajax_url,
      data: formData,
      beforeSend: function () {
        //FadeOut
        // var children = $('#category-post-content').children();
        // children.fadeOut('slow');
      },
      success: function (data) {
        //Fade in new content
        // console.log(data);
        if (postType === 'event') {
          $('#filterData').empty().append(data);
        } else {
          $('main#site-content').empty().append(data);
        }
      },
      error: function () {
        console.log('no posts found');
      }
    });
    return false;
  });


  // Hashes & tabbed pages
  // => Loading via CDN
  // }
  // remove all spans with inline font-family styles
  $('span').each(function () {
    // $(this).css('font-family', '');
    $(this).removeAttr('style');
  });

  // Video autoplay in modal
  // Gets the video src from the data-src on each button
  var $videoSrc,
    $modalLink,
    $iFrame;
  $('.modal').on('shown.bs.modal', function (e) {
    $iFrame = $(this).find('iframe');
    if ($iFrame?.length) {
      $videoSrc = $($iFrame)[0].src;

      // set the video src to autoplay and not to show related video. Youtube related video is like a box of chocolates... you never know what you're gonna get
      $($iFrame).attr('src', $videoSrc + "?rel=0&amp;showinfo=0&amp;modestbranding=1&amp;autoplay=1");
    }
  });

  $('.modal').on('hide.bs.modal', function (e) {
    if ($iFrame?.length) {
      $iFrame = $(this).find('iframe');

      // set the video src to autoplay and not to show related video. Youtube related video is like a box of chocolates... you never know what you're gonna get
      $($iFrame).attr('src', $videoSrc);
    }
  });

  $('[data-toggle="lightbox"]').on("click", function (event) {
    event.preventDefault();
    $(this).ekkoLightbox({
      alwaysShowClose: true
    });
  });

  // remove card-shadow in page carousel cards
  if ($('.flickity-carousel').find('.card-shadow').length > 0) {
    $('.flickity-carousel').find('.card-shadow').removeClass('card-shadow');
  }

  // Set tabindex to -1 for flickity-enabled elements. This is to prevent tabbing to the carousel elements
  const fe = Array.from(document.querySelectorAll('.flickity-enabled'));
  fe?.forEach((el) => {
    if (el.getAttribute('tabindex') !== '-1') {
      el.setAttribute('tabindex', '-1');
    }
  });
});

jQuery(window).on('load', function () {
  jQuery('.multi-carousel .flickity-viewport .flickity-slider').children().css("height", "100%");
  // remove 'searchApplied' flag from session storage
  if (sessionStorage.getItem('searchApplied')) {
    sessionStorage.removeItem('searchApplied');
  }
  // remove 'filterApplied' flag from session storage
  if (sessionStorage.getItem('filterApplied')) {
    sessionStorage.removeItem('filterApplied');
  }
});

function equalSizeRow() {
  var currentTallest = 0,
    currentRowStart = 0,
    rowDivs = new Array(),
    $el,
    topPosition = 0;
  // console.log('test');



  jQuery('.flickity-slider > div').each(function () {
    $el = jQuery(this);
    jQuery($el).height('auto')
    topPostion = $el.position().top;
    if (currentRowStart != topPostion) {
      for (currentDiv = 0; currentDiv < rowDivs.length; currentDiv++) {
        rowDivs[currentDiv].height(currentTallest);
      }
      rowDivs.length = 0; // empty the array
      currentRowStart = topPostion;
      currentTallest = $el.height();
      rowDivs.push($el);
    } else {
      rowDivs.push($el);
      currentTallest = (currentTallest < $el.height()) ? ($el.height()) : (currentTallest);
    }
    for (currentDiv = 0; currentDiv < rowDivs.length; currentDiv++) {
      rowDivs[currentDiv].height(currentTallest);
    }
  });

  // remove card shadow in page carousel


}

jQuery(document).ready(function () {
  jQuery('#site-navbar .dropdown-menu').each(function (el) {
    var DropdownID = 'specialID';
    var DropdownID = jQuery(this).prev().prev().attr('id');
    var DropdownID = jQuery(this).parent().children('a:eq(0)').attr('id');
    jQuery(this).attr('aria-labelledby', DropdownID);
  });
  jQuery('.dropdown-menu button.dropdown-toggle').on('click', function (e) {
    if (!jQuery(this).next().hasClass('show')) {
      jQuery(this).parents('.dropdown-menu').first().find('.show').removeClass('show');
      jQuery(this).parents('.dropdown-menu').first().find('button.dropdown-toggle').attr('aria-expanded', 'false');
    }
    jQuery(this).attr('aria-expanded',
      jQuery(this).attr('aria-expanded') == 'false' ? 'true' : 'false'
    );
    var subMenu = jQuery(this).next('.dropdown-menu');
    subMenu.toggleClass('show');
    jQuery(this).parents('li.nav-item.dropdown.show').on('hidden.bs.dropdown', function (e) {
      jQuery('.dropdown-submenu .show').removeClass('show');
      jQuery('.dropdown-menu button.dropdown-toggle').attr('aria-expanded', 'false');
    });
    return false;
  });

  // document.querySelector('nav').addEventListener('keydown', function (e) {
  //   const code = e.key;
  //   const target = e.target;
  //   // Was the arrow down key pressed?
  //   if (code == 'ArrowDown') {
  //     console.log('arrow down key pressed for: ', target.innerHTML);
  //     // Find the next anchor sibling
  //     let nextAnchor = null;
  //     // If the target is an anchor tag and does not have the class 'dropdown-toggle', get the next anchor sibling
  //     if (target.tagName === 'A') {
  //       if (target.classList.contains('dropdown-toggle')) {
  //         // If the target is an anchor tag and does not have the class 'dropdown-toggle',
  //         // get the first anchor tag of the first list item in the dropdown menu
  //         nextAnchor = target.closest('li').querySelector('ul.dropdown-menu li:first-child a');
  //       } else {
  //         nextAnchor = target.closest('li').nextElementSibling?.querySelector('a');
  //       }
  //     }
  //     nextAnchor?.focus();  // Focus the next anchor sibling
  //     // Prit the next anchor sibling to the console
  //     console.log('next anchor sibling: ', nextAnchor?.innerHTML);
  //   }
  // });
});

// Trigger the change event for the Resoure filter so that only matching resources are loaded for display
jQuery(document).ready(function ($) {

  let urlQuery = window.location.href.split('?');

  if (urlQuery.length > 1) {
    urlQuery = urlQuery[1].split('&');
    // Get the select elements on the page that have ids starting with 'resource-types'
    // const els = Array.from(document.querySelectorAll('select[id^="resource-types"]'));

    const selectId = getSelector();
    const els = Array.from(document.querySelectorAll(selectId));
    // Check if the urlQuery is defined and has a length greater than 0
    if (typeof (urlQuery) !== 'undefined' && urlQuery.length > 0) {
      // Loop through the select elements and trigger the change event for each one
      els.forEach((el) => {
        // Find a match for a select element by digging through the query string
        const idMatch = urlQuery.find(item => item.split('=')[0] === el.id);
        // Find a match for a select option by splitting the value in idMatch and finding the value of the option
        const valueMatch = Array.from(el.options).find(item => item.value === idMatch?.split('=')[1]);
        // If matches are found for both id and value, trigger the change event
        if (idMatch && valueMatch) {
          el.value = decodeURIComponent(idMatch.split('=')[1]);
          // Sleep for 500ms to allow the change event to fire
          setTimeout(() => {
            el.dispatchEvent(new Event('change'));
          }, 500);
        } else {
          el.value = '-1';
        }
      });
    }
  }
});

/**
 * A11y fixes
 * Remove empty heading tags from the page
 */
(function () {
  window.addEventListener('DOMContentLoaded', () => {
    // Get all empty heading tags on the page
    const emptyHTagsQuery = 'h1:empty, h2:empty, h3:empty, h4:empty, h5:empty, h6:empty';
    const emptyHeadings = Array.from(document.querySelectorAll(emptyHTagsQuery));
    // If there are empty heading tags on the page, remove them
    if (emptyHeadings.length > 0) {
      // Loop through the empty heading tags and remove them
      emptyHeadings.forEach((el) => {
        el.remove();
      });
      // Log the number of empty heading tags removed
      console.log(`${emptyHeadings.length} empty heading tag(s) removed from this page.`);
      console.log('Tags targeted: ', 'h1, h2, h3, h4, h5, h6');
    }
  });
})();



// Add an event listener to the window to listen for the 'load' event
(function () {
  window.addEventListener('load', () => {
    // Get the Jump Menu element by id
    const jumpMenu = document.querySelector('#jumpMenu');
    // Listen for the click event on the Jump Menu
    jumpMenu?.addEventListener('click', (e) => {
      // If the click target is an anchor tag or a span tag, get the href attribute from the anchor tag
      if (e.target.tagName === 'A' || e.target.tagName === 'SPAN') {
        // if a span is clicked, get the href attribute from the nearest anchor tag
        const target = e.target.tagName === 'SPAN' ? e.target.closest('a') : e.target;
        const href = target.getAttribute('href');
        // Check if the href attribute is a valid fragment identifier
        if (href.startsWith('#')) {
          // Prevent the default behaviour of the anchor tag
          e.preventDefault();
          const targetEl = document.querySelector(href);
          // Get the media query for the current breakpoint
          const { isMobile, isTablet } = mediaQueries();
          const scrollParams = {
            behavior: 'smooth',
            block: (isMobile || isTablet) ? 'nearest' : 'start',
            inline: 'nearest',
          }
          // Scroll to the target element with a smooth transition and offset the scroll position by 100px
          targetEl?.scrollIntoView(scrollParams);
        }
      }
    });
  });
})();

// adds event listener to clear field button in type collection pages
(function () {
  const clearSearchButton = document.getElementById('clear-search-button');
  const searchInputs = [...document.querySelectorAll('input#search-input, #news_filter_date-from, #news_filter_date-to')];
  const customSelectFields = [...document.querySelectorAll('.custom-select')];
  if (clearSearchButton) {
    clearSearchButton.addEventListener('click', () => {
      if (searchInputs) {
        searchInputs.forEach((field) => field.value = "");
      }
      if (customSelectFields) {
        customSelectFields.forEach((field) => field.value = -1);
      }
      const newURL = window.location.href.substring(0, window.location.href.indexOf("?"));
      window.location.href = newURL;
    });
  }
})();