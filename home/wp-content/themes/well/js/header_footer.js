/* This code was adapted from MacSites' WordPress Theme */

//changed to use a promise. had to use set timeout because json file was causing script to fail?
//const headFootJSON = JSON.parse(headfoot_vars);
const headFootScript = directory_uri.template_directory_uri + '/js/hfcopy.js';
function loadScript(src) {
  return new Promise(function (resolve, reject) {
    let script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.src = src;
    script.onload = () => resolve(script);
    script.onerror = () => reject(new Error(`Script load eror: ${src}`));

    document.head.appendChild(script);
  });
}
let menu_promise  = loadScript(headFootScript);
menu_promise.then(
  (resolve) => {
    // console.log(resolve);
    let headFoot = new footerheader();
    //console.log(headFoot);
      headFoot.setRoboto();

      headFoot.setSkip([{ "url": "#mcmaster-nav", "text": "Skip to McMaster Navigation" }, { "url": "#site-navbar", "text": "Skip to Site Navigation" }, { "url": "#site-content", "text": "Skip to main content" }]);
        headFoot.initialize();
        if (typeof searchCustom !== 'undefined') {
          headFoot.setSearchCustom(searchCustom);
        }
      },
  error => console.log(error)
)
