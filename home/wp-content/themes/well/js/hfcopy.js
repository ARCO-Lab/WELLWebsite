/* This code was adapted from MacSites' WordPress Theme */

!(function(c) {
    function e(a) {
        if (t[a])
            return t[a].exports;
        var s = (t[a] = {
            exports: {},
            id: a,
            loaded: !1
        });
        return c[a].call(s.exports, s, s.exports, e),
        (s.loaded = !0),
        s.exports;
    }
    var t = {};
    return (e.m = c),
    (e.c = t),
    (e.p = ""),
    e(0);
}
)([function(c, e, t) {
    c.exports = t(1);
}
, function(c, e, t) {
    "use strict";
    function a(c, e) {
        if (!(c instanceof e))
            throw new TypeError("Cannot call a class as a function");
    }
    function s(c, e) {
        return Object.freeze(Object.defineProperties(c, {
            raw: {
                value: Object.freeze(e)
            }
        }));
    }
    var n = (function() {
        function c(c, e) {
            for (var t = 0; t < e.length; t++) {
                var a = e[t];
                (a.enumerable = a.enumerable || !1),
                (a.configurable = !0),
                "value"in a && (a.writable = !0),
                Object.defineProperty(c, a.key, a);
            }
        }
        return function(e, t, a) {
            return t && c(e.prototype, t),
            a && c(e, a),
            e;
        }
        ;
    }
    )()
      , r = s(["", ""], ["", ""])
      , o = t(2);
    window.footerheader = (function() {
        function c(e) {
            a(this, c),
            (this.SVGLogo = ""),
            (this.footer = ""),
            (this.header = ""),
            (this.footerColor = "#FFF"),
            (this.headerColor = "#F1F1F1"),
            (this.linkcolor = "color:#5e6a71"),
            (this.letters = "fill: #fff"),
            (this.stringLinks = ""),
            (this.skiplinks = ""),
            (this.font = ""),
            (this.chevron = ""),
            (this.defaultCol = {
                shieldoutline: "#FFF",
                logoLetters: "fill:#FFF",
                shieldbg: "fill:#fdbf57",
                eagle: "fill: #7a003c",
                leaves: "fill:#ffbc3d",
                bookoutline: "fill:#ffbc3d",
                books: "fill: #FDBF57",
                bookspine: "fill:#7a003c",
                bookbg: "fill:#7A003C",
                shieldheader: "fill:#5e6a71",
                divider: "stroke:#fff",
                brighterworld: "fill:#fff",
                shield: "fill:#5e6a71",
            }),
            (this.blackLogoCol = {
                shieldoutline: "#FFF",
                logoLetters: "fill:#000",
                shieldbg: "fill:#000",
                eagle: "fill: #fff",
                books: "fill: #fff",
                bookspine: "fill:#000",
                shieldheader: "fill:#fff",
                shield: "fill:#5e6a71"
            }),
            (this.grayLogoCol = {
                shieldoutline: "#FFF",
                logoLetters: "fill:#5e6a71",
                shieldbg: "fill:#fdbf57",
                eagle: "fill: #7a003c",
                books: "fill: #FDBF57",
                bookspine: "fill:#7A003C",
                shieldheader: "fill:#5e6a71",
                shield: "fill:#5e6a71",
            }),
            (this.social = ""),
            (this.headerNav = ""),
            (this.logs = ""),
            (this.overlayStr = ""),
            (this.MenuItems = ""),
            (this.headerIcnsColor = ""),
            (this.stateMenu = ""),
            (this.domainSearch = ""),
            (this.searchCustomText = ""),
            (this.HeaderLogoPicker = ""),
            (this.HeaderLogo = this.getLogo(1, this.defaultCol)),
            (this.FooterLogo = this.getFooterLogo(0, this.defaultCol)),
            (this.headerColor = "#7a003c"),
            (this.headerIcnsColor = "#fff"),
            (this.footerColor = "#7a003c"),
            (this.linkcolor = "color:#FFF");
        }
        return (n(c, [{
            key: "accessiblity",
            value: function(c) {
                window.onkeyup = function(e) {
                    27 == e.keyCode && ((c.className = ""),
                    document.body.classList.contains("noscroll") && document.body.classList.remove("noscroll"));
                }
                ;
            },
        }, {
            key: "sanitize",
            value: function(c) {
                for (var e = arguments.length, t = Array(e > 1 ? e - 1 : 0), a = 1; a < e; a++)
                    t[a - 1] = arguments[a];
                var s = c.reduce(function(c, e, a) {
                    return "" + c + e + (t[a] || "");
                }, "");
                return (s = o.sanitize(s)),
                s.replace(/&/g, "&amp;").replace(/>/g, "&gt;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
            },
        }, {
            key: "getChevron",
            value: function() {
                return (this.chevron = '<svg id="chevron" xmlns="https://www.w3.org/2000/svg" viewBox="0 0 6.7 4.1"><style>.st0{fill:none;stroke:#FFFFFF;stroke-miterlimit:10;}</style><path class="st0" d="M6.4.4l-3 3-3-3"/></svg>');
            },
        }, {
            key: "initGoogleCSS",
            value: function() {
                var c = document.createElement("link");
                // (c.rel = "stylesheet"), (c.href = "//documents.mcmaster.ca/www/brighterworld/css/google-search.css"), document.getElementsByTagName("head")[0].appendChild(c);
            },
        }, {
            key: "googleSearch",
            value: function() {
                this.initGoogleCSS();
                var c = "017560809947805573293:jthpsapkwtk"
                  , e = document.createElement("script");
                (e.type = "text/javascript"),
                (e.async = !0),
                (e.src = "https://cse.google.com/cse.js?theme=ESPRESSO&cx=" + c);
                var t = document.getElementsByTagName("script")[0];
                t.parentNode.insertBefore(e, t);
            },
        }, {
            key: "gcseCallback",
            value: (function(c) {
                function e(e, t) {
                    return c.apply(this, arguments);
                }
                return ((e.toString = function() {
                    return c.toString();
                }
                ),
                e);
            }
            )(function(c, e) {
                if ("complete" != document.readyState)
                    return google.setOnLoadCallback(gcseCallback(c, e), !0);
                var t = document.getElementById("results");
                t.innerHTML = "";
                var a = document.getElementById("clearSearch")
                  , s = document.getElementById("results");
                (a.style.display = "block"),
                (s.style.display = "block"),
                google.search.cse.element.render({
                    gname: "gsearch",
                    div: "results",
                    tag: "searchresults-only",
                    attributes: {
                        linkTarget: "",
                        as_sitesearch: c
                    }
                });
                var n = google.search.cse.element.getElement("gsearch");
                n.execute(e);
            }),
        }, {
            key: "propTabParent",
            value: function(c, e) {
                for (var t, a, s = document.getElementById(c), n = s.children, r = 0; r < n.length; r++) {
                    t = n[r].children;
                    for (var o = 0; o < t.length; o++)
                        (a = t[o]),
                        1 == a.hasAttribute("href") && a.setAttribute("tabindex", e);
                }
            },
        }, {
            key: "handleTouchMove",
            value: function(c) {
                c.preventDefault();
            },
        }, {
            key: "startScrolling",
            value: function(c) {
                c.stopPropagation();
            },
        }, {
            key: "noscroll",
            value: function(c) {
                document.body;
                1 == c && (document.addEventListener("touchmove", this.handleTouchMove, !1),
                document.getElementById("mcmaster-nav").addEventListener("touchmove", this.startScrolling, !1)),
                0 == c && (document.removeEventListener("touchmove", this.handleTouchMove, !1),
                document.getElementById("mcmaster-nav").removeEventListener("touchmove", this.startScrolling));
            },
        }, {
            key: "propTabIndex",
            value: function(c, e) {
                for (var t, a = document.getElementById(c), s = a.children, n = 0; n < s.length; n++) {
                    t = s[n].children;
                    for (var r = 0; r < t.length; r++)
                        0 === e && t[r].setAttribute("tabindex", "0"),
                        1 === e && t[r].setAttribute("tabindex", "-1");
                }
            },
        }, {
            key: "propReset",
            value: function(c, e) {
                this.propTabIndex(c, 0),
                "" != e && this.propTabIndex(e, 1);
            },
        }, {
            key: "initialize",
            value: function() {
                this.googleSearch(),
                this.setWhiteHeader(),
                this.setMaroonFooter(),
                this.setSocial();
                var c = this.getstyles()
                  , e = document.createElement("style");
                (e.innerHTML = c),
                document.head.appendChild(e);
                var t = document.createElement("div")
                  , a = this.getFooter()
                  , s = this.getHeader();
                this.searchReady(),
                (t.innerHTML = a),
                document.getElementsByTagName("body")[0]?.insertAdjacentHTML("afterbegin", s),
                document.body?.appendChild(t);
                var n = this;
                this.getJson("https://documents.mcmaster.ca/www/brighterworld/json/menu.json", n).then(function(c) {
                    var e = JSON.parse(c)
                      , t = setInterval(function() {
                        if (null != document.querySelector("#mcmaster-header")) {
                            var c = function() {
                                r.classList.toggle("menu-active");
                            }
                              , a = document.createElement("ul");
                            (a.id = "mcmaster-nav"),
                            a.setAttribute("role", "menubar"),
                            a.setAttribute("aria-label", "McMaster menu");
                            var s = document.getElementById("mcmaster-search-overlay") || null;
                            s.parentNode.insertBefore(a, s.nextSibling);
                            var r = document.getElementById("mcmaster-header");
                            n.accessiblity(r),
                            r.addEventListener("toggle", c);
                            var o = document.getElementById("mcmaster-nav");
                            e.forEach(function(c) {
                                var e = c.menu
                                  , t = c.items
                                  , a = c.url
                                  , s = c.id
                                  , r = document.createElement("label")
                                  , l = document.createElement("li")
                                  , i = (document.createElement("input"),
                                document.createElement("a"));
                                i.setAttribute("href", "#"),
                                i.setAttribute("data-dparent", "sub-" + a),
                                i.setAttribute("aria-expanded", !1),
                                i.setAttribute("aria-controls", "sub-" + a),
                                i.setAttribute("class", "collapsed"),
                                (i.innerHTML = e),
                                (i.tabIndex = "-1"),
                                (r.htmlFor = s),
                                i.addEventListener("click", function(c) {
                                    var e = n.stateMenu
                                      , t = i.dataset.dparent
                                      , a = document.getElementById(t);
                                    if ((n.propReset(t, e),
                                    (a.style.height = "100%"),
                                    "" != e)) {
                                        var s = document.getElementById(e);
                                        s.style.height = 0;
                                    }
                                    c.preventDefault(),
                                    (n.stateMenu = i.dataset.dparent);
                                }),
                                i.setAttribute("role", "menuitem"),
                                l.setAttribute("role", "none"),
                                l.appendChild(i),
                                t.length > 0 && !(function() {
                                    var c = document.createElement("ul");
                                    c.setAttribute("id", "sub-" + a),
                                    c.setAttribute("aria-expanded", !1),
                                    c.setAttribute("aria-label", i.innerHTML),
                                    // get the name of the link
                                    t.forEach(function(e) {
                                        var t = e.MenuItem
                                          , a = e.url
                                          , s = document.createElement("li")
                                          , n = document.createElement("a");
                                        (n.textContent = t),
                                        n.setAttribute("href", a),
                                        (n.tabIndex = "-1"),
                                        n.setAttribute("role", "menuitem"),
                                        s.setAttribute("role", "none"),
                                        s.appendChild(n),
                                        c.setAttribute("role", "menu"),
                                        c.appendChild(s);
                                    }),
                                    t.length > 0 && (l.appendChild(c),
                                    o.appendChild(l));
                                }
                                )();
                            }),
                            clearInterval(t);
                        }
                    }, 100);
                }, function(c) {
                    console.error("Failed!", c);
                });
            },
        }, {
            key: "setWhiteHeader",
            value: function() {
                return (this.HeaderLogo = this.getLogo(1, this.grayLogoCol)),
                (this.headerIcnsColor = "#5e6a71"),
                (this.headerIcnsColorAlt = "#5e6a71"),
                (this.headerColor = "#FFF"),
                this;
            },
        }, {
            key: "setMaroonFooter",
            value: function() {
                return (this.FooterLogo = this.getFooterLogo(0, this.defaultCol)),
                (this.footerColor = "#7a003c"),
                (this.linkcolor = "color:#FFF"),
                this;
            },
        }, {
            key: "setAltLogo",
            value: function(c) {}
        }, {
            key: "getyear",
            value: function() {
                var c = new Date()
                  , e = c.getFullYear();
                return e;
            },
        }, {
            key: "setSkip",
            value: function(c) {
                if (c) {
                    var e = "";
                    for (var t in c)
                        (t = this.sanitize(r, t)),
                        c.hasOwnProperty(t) && (e = e + '<a href="' + c[t].url + '">' + c[t].text + "</a>");
                    return (this.skiplinks = '<div id="skiptocontent">' + e + "</div>"),
                    this.skiplinks;
                }
                this.skiplinks = "";
            },
        }, {
            key: "setRoboto",
            value: function() {
                return this.font = '<link href="https://fonts.googleapis.com/css?family=Roboto+Condensed:400,700" rel="stylesheet">'
            }
        }, {
            key: "setSocial",
            value: function() {
                return ((this.social = '<ul id="social--links"><li class="instagram"><a href="https://www.instagram.com/mcmasteru" target="_blank" alt=\'Instagram\' >' + ('<svg id="social-instagram" class="social" title="Instagram" alt="Instagram" style="max-width:20px; height:28px; ' + this.letters + '" xmlns="https://www.w3.org/2000/svg" width="17.14" height="17.14" viewBox="0 0 17.14 17.14"><path class="social" d="M28.57,20.23q0,2.56-.06,3.54a5.23,5.23,0,0,1-1.38,3.59,5.24,5.24,0,0,1-3.59,1.38q-1,.06-3.54.06t-3.54-.06a5.24,5.24,0,0,1-3.59-1.38,5.23,5.23,0,0,1-1.38-3.59q-.06-1-.06-3.54t.06-3.54a5.23,5.23,0,0,1,1.38-3.59,5.24,5.24,0,0,1,3.59-1.38q1-.06,3.54-.06t3.54.06a5.24,5.24,0,0,1,3.59,1.38,5.23,5.23,0,0,1,1.38,3.59Q28.57,17.67,28.57,20.23Zm-7.72-7H18l-1.08,0a8.87,8.87,0,0,0-1.15.11,4.45,4.45,0,0,0-.8.21,2.92,2.92,0,0,0-1.63,1.63,4.45,4.45,0,0,0-.21.8A8.85,8.85,0,0,0,13,17.12q0,.68,0,1.08t0,1.18c0,.52,0,.8,0,.85s0,.34,0,.85,0,.91,0,1.18,0,.63,0,1.08a8.85,8.85,0,0,0,.11,1.15,4.45,4.45,0,0,0,.21.8,2.92,2.92,0,0,0,1.63,1.63,4.52,4.52,0,0,0,.8.21,8.87,8.87,0,0,0,1.15.11l1.08,0H22l1.08,0a8.87,8.87,0,0,0,1.15-.11,4.52,4.52,0,0,0,.8-.21,2.92,2.92,0,0,0,1.63-1.63,4.45,4.45,0,0,0,.21-.8A9,9,0,0,0,27,23.34q0-.68,0-1.08t0-1.18c0-.52,0-.8,0-.85s0-.34,0-.85,0-.91,0-1.18,0-.63,0-1.08A9,9,0,0,0,26.89,16a4.45,4.45,0,0,0-.21-.8,2.92,2.92,0,0,0-1.63-1.63,4.45,4.45,0,0,0-.8-.21,8.87,8.87,0,0,0-1.15-.11l-1.08,0Zm2.26,3.92a4.42,4.42,0,0,1,0,6.23,4.42,4.42,0,0,1-6.23,0,4.42,4.42,0,0,1,0-6.23,4.42,4.42,0,0,1,6.23,0ZM22,22.25a2.86,2.86,0,1,0-4-4,2.86,2.86,0,1,0,4,4Zm3.28-7.32a1,1,0,1,1-.73-.3A1,1,0,0,1,25.3,14.93Z" transform="translate(-11.43 -11.66)"></path></svg>') + '<span class="sr-only">McMaster Instagram</span></a></li><li class="twitter"><a href="https://www.twitter.com/mcmasteru" target="_blank" alt=\'Twitter\' >' + ('<svg id="social-twitter" class="social" title="Twitter" alt="Twitter" style="max-width:20px; height:28px; ' + this.letters + '" xmlns="https://www.w3.org/2000/svg" width="17.59" height="14.29" viewBox="0 0 17.59 14.29"><path class="social" d="M28.79,14.78A7.52,7.52,0,0,1,27,16.65c0,.1,0,.26,0,.47a10.26,10.26,0,0,1-.42,2.9,10.5,10.5,0,0,1-1.29,2.77,10.89,10.89,0,0,1-2.06,2.35,9.16,9.16,0,0,1-2.88,1.63,10.52,10.52,0,0,1-3.61.61,10,10,0,0,1-5.54-1.62,7.6,7.6,0,0,0,.87,0,7.06,7.06,0,0,0,4.47-1.54,3.61,3.61,0,0,1-3.37-2.5,4.58,4.58,0,0,0,.68.06,3.72,3.72,0,0,0,.95-.12,3.54,3.54,0,0,1-2.07-1.24,3.48,3.48,0,0,1-.82-2.29v0a3.58,3.58,0,0,0,1.63.46,3.6,3.6,0,0,1-1.17-1.28,3.61,3.61,0,0,1,.06-3.54,10.23,10.23,0,0,0,3.29,2.66,10,10,0,0,0,4.15,1.11,4,4,0,0,1-.09-.83A3.61,3.61,0,0,1,26,14.22a7.07,7.07,0,0,0,2.29-.87,3.5,3.5,0,0,1-1.58,2A7.16,7.16,0,0,0,28.79,14.78Z" transform="translate(-11.21 -13.09)"></path></svg>') + '<span class="sr-only">McMaster Twitter</span></a></li><li class="facebook"><a href="https://www.facebook.com/mcmasteruniversity" target="_blank" alt="Facebook">' + ('<svg id="social-facebook" class="social" title="Facebook" alt="Facebook" style="max-width:20px; height:28px; ' + this.letters + '" xmlns="https://www.w3.org/2000/svg" width="9.64" height="18.57" viewBox="0 0 9.64 18.57"><g id="social" data-name="Facebook"><path class="185192d7-0a1f-47bf-be6a-a075f203b0c8" d="M25,10.36v2.95H23.24a1.64,1.64,0,0,0-1.29.4,1.84,1.84,0,0,0-.33,1.21V17h3.27l-.44,3.3H21.61V28.8H18.19V20.33H15.35V17h2.85V14.59a4.32,4.32,0,0,1,1.16-3.22,4.21,4.21,0,0,1,3.09-1.14A18.54,18.54,0,0,1,25,10.36Z" transform="translate(-15.35 -10.23)"></path></g></svg>') + '<span class="sr-only">McMaster Facebook</span></a></li><li class="youtube">' + ('<a href="https://www.youtube-nocookie.com/mcmasterutv" target="_blank" alt="YouTube" class="' + this.linkcolor + '">') + ('<svg id="social-youtube" class="social" title="YouTube" alt="YouTube" style="max-width:18px; height:28px; ' + this.letters + '" xmlns="https://www.w3.org/2000/svg" width="20" height="14.06" viewBox="0 0 20 14.06"><g id="social-yt" data-name="YouTube"><path class="51d5e5b1-33b4-43d8-989b-82c83fa0ef0e" d="M20,13.2q1.88,0,3.62,0t2.56.11l.82,0,.19,0,.26,0,.26.05a1.5,1.5,0,0,1,.32.09l.31.15a2.17,2.17,0,0,1,.35.22,2.68,2.68,0,0,1,.32.3l.17.21a3.74,3.74,0,0,1,.32.65,4.23,4.23,0,0,1,.3,1.13q.09.71.14,1.52T30,19v2a23.52,23.52,0,0,1-.2,3.24,4.45,4.45,0,0,1-.28,1.11,2.88,2.88,0,0,1-.36.69l-.16.19a2.68,2.68,0,0,1-.32.3,1.83,1.83,0,0,1-.35.21l-.31.14a1.5,1.5,0,0,1-.32.09l-.27.05-.26,0L27,27q-2.8.21-7,.21-2.31,0-4-.07t-2.24-.08l-.55,0-.4,0a5.51,5.51,0,0,1-.61-.11,3.42,3.42,0,0,1-.57-.23,2.24,2.24,0,0,1-.63-.46L10.82,26a3.74,3.74,0,0,1-.32-.65,4.23,4.23,0,0,1-.3-1.13q-.09-.71-.14-1.52T10,21.43v-2a23.67,23.67,0,0,1,.2-3.24,4.45,4.45,0,0,1,.28-1.11,2.85,2.85,0,0,1,.36-.69l.16-.19a2.75,2.75,0,0,1,.32-.3,2.17,2.17,0,0,1,.35-.22l.31-.15a1.52,1.52,0,0,1,.32-.09l.26-.05.26,0,.19,0Q15.8,13.2,20,13.2Zm-2.06,9.62L23.34,20l-5.4-2.82Z" transform="translate(-10 -13.2)"></path></g></svg>') + '<span class="sr-only">McMaster YouTube</span></a></li><li class="linkedin"><a href="https://www.linkedin.com/school/164897/" target="_blank" alt=\'LinkedIn\' >' + ('<svg id="social-linkedin" class="social" alt="LinkedIn" style="max-width:16px; height:28px; ' + this.letters + '" title="LinkedIn" xmlns="https://www.w3.org/2000/svg" width="17.14" height="16.38" viewBox="0 0 17.14 16.38"><path class="social" d="M15.56,13.79A1.76,1.76,0,0,1,15,15.15a2.1,2.1,0,0,1-1.51.55h0A2,2,0,0,1,12,15.15a1.83,1.83,0,0,1-.56-1.36A1.8,1.8,0,0,1,12,12.42a2.1,2.1,0,0,1,1.5-.54,2,2,0,0,1,1.48.54A1.86,1.86,0,0,1,15.56,13.79Zm-.23,3.42V28.26H11.64V17.2Zm13.25,4.72v6.34H24.9V22.35a3.23,3.23,0,0,0-.45-1.84A1.59,1.59,0,0,0,23,19.85a1.81,1.81,0,0,0-1.18.39,2.37,2.37,0,0,0-.71,1,2.69,2.69,0,0,0-.12.9v6.17H17.36q0-4.45,0-7.22t0-3.3V17.2H21v1.61h0a4.19,4.19,0,0,1,1.09-1.21,2.9,2.9,0,0,1,1-.49,4.43,4.43,0,0,1,1.28-.17,4,4,0,0,1,3.07,1.27A5.32,5.32,0,0,1,28.57,21.92Z" transform="translate(-11.43 -11.88)"></path></svg>') + '<span class="sr-only">McMaster LinkedIn</span></a></li></ul>'),
                this);
            },
        }, {
            key: "setLogo",
            value: function(c) {
                return "st-joes" == c && (this.HeaderLogoPicker = "st-joes"),
                this;
            },
        }, {
            key: "setTitle",
            value: function(c) {
                for (var e in c)
                    c[e] = this.sanitize(r, c[e]);
                if (c.image)
                    c.titleUrl ? (this.title = '<a href="' + c.titleUrl + '"><img class="mcmaster-header__site-logo" src="' + c.image + '" alt="Logo for ' + c.title + '"></a>') : (this.title = '<img class="mcmaster-header__site-logo" src="' + c.image + '" alt="Logo for ' + c.title + '">');
                else if (c.title) {
                    var t = "title-only";
                    (this.title = ""),
                    c.subtitle && !c.tagline && (c.subtitleUrl ? (this.title += '<h2 class="mcmaster-header__department"><a href="' + c.subtitleUrl + '">' + c.subtitle + "</a></h2>\n") : (this.title += '<h2 class="mcmaster-header__department">' + c.subtitle + "</h2>\n"),
                    (t = "")),
                    c.tagline && (t = "has-tagline"),
                    c.titleUrl ? (this.title += '<h1 class="mcmaster-header__header-title ' + t + '"><a href="' + c.titleUrl + '">' + c.title + "</a></h1>\n") : (this.title += '<h1 class="mcmaster-header__header-title ' + t + '">' + c.title + "</h1>\n"),
                    c.tagline && (this.title += '<h2 class="mcmaster-header__tagline">' + c.tagline + "</h2>\n");
                } else
                    this.title = "";
                return this.title;
            },
        }, {
            key: "getLogo",
            value: function(c, e) {
                var t = "";
                return ((t = "width: 140px; height: 80px; margin-top: 5px;"),
                1 == c && (t = "width: 140px; height: 80px; margin: 0 10px;"),
                "st-joes" == this.HeaderLogoPicker ? (this.SVGLogo = '<svg id="mcmaster-logo-header-st-joes" data-name="mcmaster-logo-header" xmlns="https://www.w3.org/2000/svg" width="166.51" height="42.96" viewBox="0 0 166.51 42.96" style="width:auto;height:56px;margin-top:8px;">\n  <defs>\n    <style>\n      .cls-1 {\n        fill: #36b0c9;\n      }\n\n      .cls-2 {\n        fill: #003057;\n      }\n\n      .cls-3 {\n        fill: #495965;\n      }\n\n      .cls-4, .cls-8 {\n        fill: none;\n      }\n\n      .cls-5 {\n        fill: #fff;\n      }\n\n      .cls-6 {\n        fill: #7a003c;\n        stroke: #7a003c;\n      }\n\n      .cls-6, .cls-7 {\n        stroke-width: 0.09px;\n      }\n\n      .cls-7 {\n        fill: #fec057;\n        stroke: #fec057;\n      }\n\n      .cls-8 {\n        stroke: #495965;\n        stroke-width: 0.4px;\n      }\n    </style>\n  </defs>\n  <title>mac-st-joes</title>\n  <g>\n    <g>\n      <path class="cls-1" d="M138.4,25.66c0-.54,0-1.14,0-1.81s0-1.29,0-1.82c0-.35,0-.6,0-.73s0-.23,0-.29a2.82,2.82,0,0,0,.42,0,2.68,2.68,0,0,0,.42,0s0,.15,0,.28,0,.38,0,.74,0,.87,0,1.35c.49,0,1,.07,1.67.07s1.18,0,1.67-.07l0-1.35c0-.36,0-.6,0-.74s0-.23,0-.28a2.68,2.68,0,0,0,.42,0,2.82,2.82,0,0,0,.42,0c0,.06,0,.15,0,.29s0,.38,0,.73c0,.54,0,1.14,0,1.81s0,1.29,0,1.82c0,.36,0,.6,0,.73a2.9,2.9,0,0,0,0,.29,2.82,2.82,0,0,0-.42,0,2.68,2.68,0,0,0-.42,0c0-.05,0-.15,0-.28s0-.38,0-.74c0-.51,0-1.09,0-1.74-.49,0-1-.06-1.67-.06s-1.18,0-1.66.06c0,.65,0,1.23,0,1.74,0,.36,0,.6,0,.74s0,.23,0,.28a2.68,2.68,0,0,0-.42,0,2.82,2.82,0,0,0-.42,0,2.9,2.9,0,0,0,0-.29c0-.13,0-.37,0-.73"/>\n      <path class="cls-1" d="M145.1,26.76a1.16,1.16,0,0,1-.83-.3,1,1,0,0,1-.32-.76.94.94,0,0,1,.29-.71,1.57,1.57,0,0,1,.84-.39l1-.2a.38.38,0,0,0,.24-.11.4.4,0,0,0,.06-.25V24a1.08,1.08,0,0,0-.24-.76.9.9,0,0,0-.71-.26,1.3,1.3,0,0,0-.65.15,1,1,0,0,0-.4.49h-.1v-.46a2,2,0,0,1,.6-.34,1.85,1.85,0,0,1,.67-.13,1.59,1.59,0,0,1,1.08.34,1.27,1.27,0,0,1,.38,1v2.09a.55.55,0,0,0,.06.29.2.2,0,0,0,.19.1h.14l0,.18a1.12,1.12,0,0,1-.59.13.4.4,0,0,1-.36-.21.91.91,0,0,1-.11-.33,1.5,1.5,0,0,1-.31.24,1.77,1.77,0,0,1-1,.3m1.3-2.11-.77.15a1.57,1.57,0,0,0-.7.29.7.7,0,0,0-.23.53.69.69,0,0,0,.19.52.73.73,0,0,0,.54.18,1.22,1.22,0,0,0,.67-.18,1.07,1.07,0,0,0,.3-.3Z"/>\n      <path class="cls-1" d="M147.72,26c0-.37,0-.8,0-1.27s0-.88,0-1.25a4.48,4.48,0,0,0,0-.46c0-.1,0-.18,0-.25a2.05,2.05,0,0,0,.37,0,2.17,2.17,0,0,0,.38,0,.23.23,0,0,0,0,.13,2.86,2.86,0,0,0,0,.3l0,.24a1.69,1.69,0,0,1,.22-.29,1.33,1.33,0,0,1,1-.46,1.16,1.16,0,0,1,.9.36,1.1,1.1,0,0,1,.26.46,2.09,2.09,0,0,1,.26-.36,1.33,1.33,0,0,1,1-.46,1.16,1.16,0,0,1,.9.36,1.35,1.35,0,0,1,.34,1v.71c0,.47,0,.9,0,1.27a4.32,4.32,0,0,0,0,.46c0,.1,0,.18,0,.25a2.3,2.3,0,0,0-.39,0,2.24,2.24,0,0,0-.38,0,.88.88,0,0,0,0-.24c0-.1,0-.25,0-.47s0-.8,0-1.27v-.62a1.14,1.14,0,0,0-.22-.72.76.76,0,0,0-.6-.26.9.9,0,0,0-.75.34,1.66,1.66,0,0,0-.25,1v.28c0,.47,0,.9,0,1.27a4.32,4.32,0,0,0,0,.46,1.56,1.56,0,0,0,0,.25,2.3,2.3,0,0,0-.39,0,2.24,2.24,0,0,0-.38,0c0-.07,0-.15,0-.25a4.32,4.32,0,0,0,0-.46c0-.37,0-.8,0-1.27v-.62a1.14,1.14,0,0,0-.21-.72.76.76,0,0,0-.6-.26.9.9,0,0,0-.75.34,1.59,1.59,0,0,0-.25,1v.28c0,.47,0,.9,0,1.27s0,.37,0,.47a1.5,1.5,0,0,0,0,.24,2.42,2.42,0,0,0-.39,0,2.24,2.24,0,0,0-.38,0c0-.07,0-.15,0-.25a4.32,4.32,0,0,0,0-.46"/>\n      <path class="cls-1" d="M154.75,20.91a.41.41,0,0,1,.3.12.38.38,0,0,1,.12.29.41.41,0,0,1-.42.42.4.4,0,0,1-.29-.12.41.41,0,0,1-.12-.3.38.38,0,0,1,.12-.29.4.4,0,0,1,.29-.12M154.41,26c0-.37,0-.8,0-1.27s0-.88,0-1.25a4.48,4.48,0,0,0,0-.46c0-.1,0-.18,0-.25a2.21,2.21,0,0,0,.39,0,2.25,2.25,0,0,0,.38,0,1,1,0,0,0,0,.26,4.24,4.24,0,0,0,0,.45V24.7c0,.47,0,.9,0,1.27s0,.37,0,.46a1.45,1.45,0,0,0,0,.25,2.36,2.36,0,0,0-.39,0,2.24,2.24,0,0,0-.38,0c0-.07,0-.15,0-.25A4.32,4.32,0,0,0,154.41,26Z"/>\n      <path class="cls-1" d="M156.11,26c0-.68,0-1.47,0-2.38l0-2.36c0-.21,0-.37,0-.46a1.19,1.19,0,0,0,0-.24,2.21,2.21,0,0,0,.39,0,2.25,2.25,0,0,0,.38,0s0,.12,0,.21,0,.26,0,.49c0,.68,0,1.46,0,2.36l0,2.38c0,.2,0,.34,0,.44a2.51,2.51,0,0,0,0,.27,2.36,2.36,0,0,0-.39,0,2.24,2.24,0,0,0-.38,0c0-.05,0-.13,0-.23s0-.25,0-.48"/>\n      <path class="cls-1" d="M159.17,26.61a1.21,1.21,0,0,1-.6.15.92.92,0,0,1-.71-.25,1.1,1.1,0,0,1-.22-.76V23.12h-.33l-.09,0-.09,0c0-.1,0-.18,0-.25s0-.16,0-.26l.09,0,.09,0,.33,0v-.22c0-.12,0-.24,0-.36a1,1,0,0,0-.05-.25l.4-.14.37-.2a2,2,0,0,0-.05.31c0,.16,0,.32,0,.49v.37l.69,0,.09,0,.09,0c0,.1,0,.18,0,.26s0,.15,0,.25l-.09,0-.09,0-.69,0v2.64a.82.82,0,0,0,.14.53.52.52,0,0,0,.42.18.68.68,0,0,0,.33-.09.49.49,0,0,0,0,.12.57.57,0,0,0,0,.12"/>\n      <path class="cls-1" d="M159.52,26.2a2.27,2.27,0,0,1,0-3,1.93,1.93,0,0,1,1.47-.58,1.81,1.81,0,0,1,1.37.56,2.28,2.28,0,0,1,0,3,2,2,0,0,1-1.47.58,1.82,1.82,0,0,1-1.38-.56m2.33-.23a2.31,2.31,0,0,0,.33-1.31,2.13,2.13,0,0,0-.31-1.26A1.05,1.05,0,0,0,161,23a1,1,0,0,0-.89.49,2.35,2.35,0,0,0-.33,1.32,2.17,2.17,0,0,0,.32,1.26,1,1,0,0,0,.9.43A1,1,0,0,0,161.85,26Z"/>\n      <path class="cls-1" d="M163.19,26c0-.37,0-.8,0-1.27s0-.88,0-1.25,0-.4,0-.5a1.06,1.06,0,0,0,0-.21,2,2,0,0,0,.37,0,2.05,2.05,0,0,0,.37,0,.21.21,0,0,0,0,.12c0,.06,0,.16,0,.31l0,.23a3.45,3.45,0,0,1,.23-.28,1.44,1.44,0,0,1,1.09-.46,1.28,1.28,0,0,1,1,.38,1.41,1.41,0,0,1,.36,1V26a3.22,3.22,0,0,0,0,.33c0,.09,0,.22,0,.38a2.36,2.36,0,0,0-.39,0,2.24,2.24,0,0,0-.38,0,1.57,1.57,0,0,0,0-.24c0-.1,0-.25,0-.47,0-.38,0-.8,0-1.26v-.46a1.31,1.31,0,0,0-.25-.84.89.89,0,0,0-.71-.31.91.91,0,0,0-.76.33,1.61,1.61,0,0,0-.25,1v.28c0,.47,0,.9,0,1.27s0,.37,0,.46,0,.18,0,.25a3.62,3.62,0,0,0-.76,0c0-.07,0-.15,0-.25s0-.24,0-.46"/>\n      <path class="cls-2" d="M135.11,25.66a3.83,3.83,0,0,0-1.18-1,2.39,2.39,0,0,1,.62,1,2.1,2.1,0,0,1-.13,1.11,5.81,5.81,0,0,1-1.39,1.9,23.06,23.06,0,0,1-2,1.63s0,0,0,0,0,.26.07.56a7.28,7.28,0,0,1,0,.93,13.3,13.3,0,0,0,1.79-1.11,9,9,0,0,0,1.38-1.25,5.29,5.29,0,0,0,.9-1.35,3.28,3.28,0,0,0,.27-1.14,2.58,2.58,0,0,0-.36-1.29"/>\n      <path class="cls-1" d="M134.72,22.3s-.18.25-.38.48a4,4,0,0,1-.4.43s0-.54,0-1a7.51,7.51,0,0,0-.09-.87s-.36.34-.7.64-.62.54-.62.54,0,1.58,0,1.68-.44.17-.46.19,0,.2,0,.38a3.07,3.07,0,0,1-.09.48s.45-.13.45-.12a6.44,6.44,0,0,1-.67,2.29,3.16,3.16,0,0,1-1.47,1.2,5.51,5.51,0,0,0,1.63-.86,4.65,4.65,0,0,0,1-1.09,7.37,7.37,0,0,0,.55-1.07,6.77,6.77,0,0,0,.31-1.08,5.26,5.26,0,0,0,.47-.36c.24-.2.48-.45.49-.46a3.78,3.78,0,0,0,.08-.79,3,3,0,0,0-.08-.62"/>\n      <path class="cls-2" d="M135,18.79a3.32,3.32,0,0,1-.08-.5,5.8,5.8,0,0,1,0-.83,13.93,13.93,0,0,0-1.79,1,9.32,9.32,0,0,0-1.38,1.13,4.74,4.74,0,0,0-.9,1.21,2.73,2.73,0,0,0-.27,1,2.13,2.13,0,0,0,.36,1.16,3.82,3.82,0,0,0,1.18.91,2.12,2.12,0,0,1-.62-.9,1.7,1.7,0,0,1,.13-1A5.27,5.27,0,0,1,133,20.29a22,22,0,0,1,2-1.47s0,0,0,0"/>\n      <path class="cls-2" d="M95.59,25.59c0-.55,0-1.15,0-1.82s0-1.28,0-1.82c0-.35,0-.59,0-.73s0-.23,0-.28L96,21l.42,0a2.6,2.6,0,0,0,0,.28c0,.13,0,.38,0,.73s0,.87,0,1.36c.49,0,1,.06,1.66.06s1.19,0,1.68-.06l0-1.36c0-.35,0-.6,0-.73a1.52,1.52,0,0,0,0-.28l.42,0,.41,0a1.6,1.6,0,0,0,0,.28c0,.14,0,.38,0,.73,0,.54,0,1.15,0,1.82s0,1.28,0,1.82c0,.35,0,.59,0,.73a1.6,1.6,0,0,0,0,.28l-.41,0-.42,0a1.52,1.52,0,0,0,0-.28c0-.13,0-.38,0-.73,0-.52,0-1.1,0-1.74A16.63,16.63,0,0,0,98,23.78c-.62,0-1.18,0-1.67.07,0,.64,0,1.22,0,1.74,0,.35,0,.6,0,.73a2.6,2.6,0,0,0,0,.28l-.42,0-.42,0c0-.05,0-.15,0-.28s0-.38,0-.73"/>\n      <path class="cls-2" d="M103,26.68a1.75,1.75,0,0,1-1.36-.56,2.08,2.08,0,0,1-.52-1.46,2.18,2.18,0,0,1,.51-1.5,1.69,1.69,0,0,1,1.32-.57h0a1.64,1.64,0,0,1,1.26.46,1.84,1.84,0,0,1,.43,1.15,2.71,2.71,0,0,1,0,.29v.22h0l-.58-.05-.82,0h-1.4v.16a1.8,1.8,0,0,0,.35,1.18,1.23,1.23,0,0,0,1,.41,1.71,1.71,0,0,0,.71-.15,2.18,2.18,0,0,0,.61-.46l.07.09c0,.07,0,.13,0,.18s0,.11,0,.18a2.52,2.52,0,0,1-.7.34,3,3,0,0,1-.81.11m.9-2.39v-.16a1.45,1.45,0,0,0-.26-.91.84.84,0,0,0-.7-.34.87.87,0,0,0-.81.48,2.4,2.4,0,0,0-.26.93Z"/>\n      <path class="cls-2" d="M105.73,26.68a1.17,1.17,0,0,1-.82-.29,1,1,0,0,1-.32-.76.94.94,0,0,1,.29-.72,1.57,1.57,0,0,1,.84-.39l1-.19a.45.45,0,0,0,.24-.11A.43.43,0,0,0,107,24V23.9a1.08,1.08,0,0,0-.24-.76,1,1,0,0,0-.72-.26,1.17,1.17,0,0,0-.64.16,1.14,1.14,0,0,0-.41.48h-.09v-.47a2.18,2.18,0,0,1,.6-.34,2,2,0,0,1,.66-.12,1.58,1.58,0,0,1,1.09.34,1.24,1.24,0,0,1,.37,1V26a.6.6,0,0,0,.07.3.19.19,0,0,0,.18.1l.15,0,0,.18a1.05,1.05,0,0,1-.59.13.42.42,0,0,1-.37-.21,1.48,1.48,0,0,1-.11-.32,1.22,1.22,0,0,1-.3.24,1.88,1.88,0,0,1-1,.29m1.31-2.1-.77.14a1.42,1.42,0,0,0-.7.3.64.64,0,0,0-.23.53.69.69,0,0,0,.18.51.77.77,0,0,0,.54.18,1.25,1.25,0,0,0,.68-.18,1.07,1.07,0,0,0,.3-.3Z"/>\n      <path class="cls-2" d="M108.55,25.89q0-1,0-2.37l0-2.36c0-.22,0-.37,0-.47a.88.88,0,0,0,0-.24,2.17,2.17,0,0,0,.38,0,2.09,2.09,0,0,0,.38,0,1.09,1.09,0,0,0,0,.22,4.88,4.88,0,0,0,0,.49c0,.67,0,1.46,0,2.35l0,2.38c0,.2,0,.35,0,.44l0,.27-.38,0-.38,0c0-.05,0-.13,0-.22s0-.26,0-.49"/>\n      <path class="cls-2" d="M111.62,26.53a1.28,1.28,0,0,1-.61.15.93.93,0,0,1-.7-.24,1.12,1.12,0,0,1-.23-.77V23l-.32,0h-.09l-.09.05a3.38,3.38,0,0,0,0-.52.19.19,0,0,0,.09,0,.15.15,0,0,0,.09,0l.32,0v-.21c0-.13,0-.24,0-.36a1.52,1.52,0,0,0,0-.25,2.68,2.68,0,0,0,.39-.15,2.86,2.86,0,0,0,.38-.2,1.32,1.32,0,0,0-.05.32c0,.15,0,.32,0,.49v.37c.27,0,.5,0,.7,0a.18.18,0,0,0,.09,0l.09,0a1.7,1.7,0,0,0,0,.52l-.09-.05h-.09c-.2,0-.43,0-.7,0v2.64a.85.85,0,0,0,.15.54.52.52,0,0,0,.42.18.6.6,0,0,0,.33-.1.72.72,0,0,0,0,.24"/>\n      <path class="cls-2" d="M111.76,25.89c0-.68,0-1.47,0-2.37s0-1.68,0-2.36c0-.23,0-.4,0-.49s0-.17,0-.22a2.17,2.17,0,0,0,.38,0,2.05,2.05,0,0,0,.37,0,3.66,3.66,0,0,0-.07.62c0,.24,0,.62,0,1.15v1.12a2.43,2.43,0,0,1,.24-.3,1.44,1.44,0,0,1,1.08-.45,1.26,1.26,0,0,1,1,.37,1.41,1.41,0,0,1,.36,1v1.91a3.22,3.22,0,0,0,0,.33c0,.1,0,.22,0,.38l-.39,0-.38,0a.88.88,0,0,0,0-.24c0-.1,0-.25,0-.47,0-.37,0-.79,0-1.26v-.38a1.5,1.5,0,0,0-.24-.9.83.83,0,0,0-.68-.32,1,1,0,0,0-.79.33,1.6,1.6,0,0,0-.26,1l0,1.54c0,.2,0,.35,0,.44s0,.19,0,.27l-.39,0-.38,0c0-.05,0-.13,0-.22s0-.26,0-.49"/>\n      <path class="cls-2" d="M118.69,26l-.07.36a1.84,1.84,0,0,1-.58.28,2.58,2.58,0,0,1-.7.09,1.92,1.92,0,0,1-2-2,2.07,2.07,0,0,1,.57-1.51,2,2,0,0,1,1.49-.57,2.89,2.89,0,0,1,.7.08,3.35,3.35,0,0,1,.69.25c0,.11-.07.21-.1.3s0,.19-.07.31h-.12a1.14,1.14,0,0,0-.44-.48,1.24,1.24,0,0,0-.63-.17,1.14,1.14,0,0,0-1,.5,2.2,2.2,0,0,0-.36,1.32,1.76,1.76,0,0,0,.42,1.21,1.32,1.32,0,0,0,1,.48,1.3,1.3,0,0,0,.58-.14,1.7,1.7,0,0,0,.51-.4l.07.1"/>\n      <path class="cls-2" d="M119.87,26.68a1.2,1.2,0,0,1-.83-.29,1,1,0,0,1-.31-.76,1,1,0,0,1,.28-.72,1.61,1.61,0,0,1,.85-.39l1-.19a.53.53,0,0,0,.25-.11.43.43,0,0,0,.06-.26V23.9a1,1,0,0,0-.25-.76.94.94,0,0,0-.71-.26,1.17,1.17,0,0,0-.64.16,1.08,1.08,0,0,0-.41.48h-.09v-.47a2.18,2.18,0,0,1,.6-.34,2,2,0,0,1,.66-.12,1.54,1.54,0,0,1,1.08.34,1.22,1.22,0,0,1,.38,1V26a.51.51,0,0,0,.07.3.19.19,0,0,0,.18.1l.15,0,0,.18a1.05,1.05,0,0,1-.59.13.42.42,0,0,1-.37-.21,1.08,1.08,0,0,1-.11-.32,1.76,1.76,0,0,1-.3.24,1.88,1.88,0,0,1-1,.29m1.31-2.1-.77.14a1.42,1.42,0,0,0-.7.3.65.65,0,0,0-.24.53.69.69,0,0,0,.19.51.77.77,0,0,0,.54.18,1.22,1.22,0,0,0,.67-.18,1.26,1.26,0,0,0,.31-.3Z"/>\n      <path class="cls-2" d="M122.59,25.89c0-.37,0-.79,0-1.27s0-.88,0-1.25c0-.21,0-.36,0-.46a1.5,1.5,0,0,0,0-.24,2.62,2.62,0,0,0,.41,0,2.49,2.49,0,0,0,.4,0c0,.06,0,.13,0,.23s0,.25,0,.47v0a2.13,2.13,0,0,1,.23-.33,1.11,1.11,0,0,1,.84-.48h.16a.35.35,0,0,1,.14,0,2.28,2.28,0,0,0-.11.35,1.86,1.86,0,0,0,0,.36,1,1,0,0,0-.21-.09.82.82,0,0,0-.23,0,.68.68,0,0,0-.61.31,1.58,1.58,0,0,0-.22.92v.16c0,.48,0,.9,0,1.27s0,.41,0,.5a1.06,1.06,0,0,0,0,.21l-.38,0-.39,0a1.45,1.45,0,0,0,0-.25c0-.09,0-.24,0-.46"/>\n      <path class="cls-2" d="M126.17,26.68a1.72,1.72,0,0,1-1.35-.56,2,2,0,0,1-.52-1.46,2.23,2.23,0,0,1,.5-1.5,1.7,1.7,0,0,1,1.33-.57h0a1.64,1.64,0,0,1,1.26.46,1.78,1.78,0,0,1,.43,1.15,2.71,2.71,0,0,1,0,.29v.22h0l-.59-.05-.81,0H125v.16a1.75,1.75,0,0,0,.35,1.18,1.22,1.22,0,0,0,1,.41,1.64,1.64,0,0,0,.71-.15,1.93,1.93,0,0,0,.61-.46l.07.09c0,.07,0,.13,0,.18s0,.11,0,.18a2.4,2.4,0,0,1-.7.34,3,3,0,0,1-.81.11m.91-2.39v-.16a1.45,1.45,0,0,0-.27-.91.83.83,0,0,0-.7-.34.88.88,0,0,0-.81.48,2.41,2.41,0,0,0-.25.93Z"/>\n      <path class="cls-2" d="M101.36,4.68a2.61,2.61,0,0,0-.93-1,2.44,2.44,0,0,0-1.26-.35,2.21,2.21,0,0,0-1.59.58A2,2,0,0,0,97,5.44a1.85,1.85,0,0,0,.6,1.39,4.84,4.84,0,0,0,1.89,1,5.43,5.43,0,0,1,2.34,1.37,3.1,3.1,0,0,1,.69,2.11,3.6,3.6,0,0,1-1.15,2.7,3.89,3.89,0,0,1-2.81,1.1,5.58,5.58,0,0,1-1.82-.27,3.2,3.2,0,0,1-1.28-.81c.07-.24.12-.44.16-.61s.07-.38.1-.61l.28-.09a3.12,3.12,0,0,0,1.14,1.17,3,3,0,0,0,1.56.46,2.5,2.5,0,0,0,1.82-.7,2.44,2.44,0,0,0,.71-1.8,2.07,2.07,0,0,0-.6-1.51A4.67,4.67,0,0,0,98.7,9.3a5.64,5.64,0,0,1-2.37-1.36,3,3,0,0,1-.7-2.07,3.07,3.07,0,0,1,1-2.34,3.53,3.53,0,0,1,2.51-1,5.25,5.25,0,0,1,1.51.2,4.49,4.49,0,0,1,1.3.58c-.08.26-.15.48-.2.66s-.11.41-.17.67h-.25"/>\n      <path class="cls-2" d="M107,14.78a2.58,2.58,0,0,1-1.29.33,2,2,0,0,1-1.51-.53,2.4,2.4,0,0,1-.49-1.64V7.29c-.24,0-.48,0-.7,0a.5.5,0,0,0-.19,0,.48.48,0,0,0-.19.09c0-.21,0-.4,0-.55s0-.35,0-.56a.56.56,0,0,0,.19.09.46.46,0,0,0,.19,0l.7,0V6.05a6.51,6.51,0,0,0,0-.77,2.07,2.07,0,0,0-.09-.53c.33-.11.61-.22.84-.32s.5-.25.8-.43a3.05,3.05,0,0,0-.09.68c0,.33,0,.68,0,1.05v.79c.56,0,1.06,0,1.48,0a.51.51,0,0,0,.2,0,.48.48,0,0,0,.19-.09c0,.21,0,.4,0,.56s0,.34,0,.55a.48.48,0,0,0-.19-.09.5.5,0,0,0-.19,0c-.43,0-.93-.05-1.49-.05v5.67a1.78,1.78,0,0,0,.31,1.14,1.06,1.06,0,0,0,.9.4,1.32,1.32,0,0,0,.7-.21,2.36,2.36,0,0,0,0,.25,2.54,2.54,0,0,0,0,.26"/>\n      <path class="cls-2" d="M108.52,13.06a1,1,0,0,1,.73.3,1,1,0,0,1,.29.73,1,1,0,0,1-1.75.72.94.94,0,0,1-.29-.72,1,1,0,0,1,1-1"/>\n      <path class="cls-2" d="M115.21,8.21q0-2.79,0-3.87a14.19,14.19,0,0,0-.1-1.57,8.28,8.28,0,0,0,.9,0,7.85,7.85,0,0,0,.89,0,12.49,12.49,0,0,0-.14,1.64c0,.72,0,2,0,3.8l0,1.92.08,3.19a4.38,4.38,0,0,1-.94,3.09,3.57,3.57,0,0,1-2.68,1.06l-.12-.64a2,2,0,0,0,1.65-.78,4.42,4.42,0,0,0,.54-2.54l0-3.37V8.21"/>\n      <path class="cls-2" d="M119.12,13.91A4.37,4.37,0,0,1,118,10.78a4.41,4.41,0,0,1,1.22-3.23,4.2,4.2,0,0,1,3.15-1.24,3.89,3.89,0,0,1,3,1.2,4.35,4.35,0,0,1,1.14,3.13,4.44,4.44,0,0,1-1.21,3.23,4.21,4.21,0,0,1-3.16,1.24,3.89,3.89,0,0,1-3-1.2m5-.49a5,5,0,0,0,.72-2.83,4.6,4.6,0,0,0-.68-2.7,2.23,2.23,0,0,0-1.94-.95A2.18,2.18,0,0,0,120.31,8a5,5,0,0,0-.72,2.83,4.6,4.6,0,0,0,.68,2.7,2.26,2.26,0,0,0,2,1A2.2,2.2,0,0,0,124.12,13.42Z"/>\n      <path class="cls-2" d="M131.07,8.1a1.94,1.94,0,0,0-.68-.87,1.7,1.7,0,0,0-1-.31,1.45,1.45,0,0,0-1.06.41,1.42,1.42,0,0,0-.41,1.05,1.26,1.26,0,0,0,.42,1,3.3,3.3,0,0,0,1.38.62,4.19,4.19,0,0,1,1.8.83,1.91,1.91,0,0,1,.52,1.44,2.66,2.66,0,0,1-.89,2,3.13,3.13,0,0,1-2.19.83,5.05,5.05,0,0,1-1.37-.16,2.54,2.54,0,0,1-1-.47c.11-.24.2-.45.27-.62s.15-.39.23-.64a2.46,2.46,0,0,0,.85.95,2.28,2.28,0,0,0,1.19.32,1.76,1.76,0,0,0,1.26-.44,1.48,1.48,0,0,0,.5-1.14,1.25,1.25,0,0,0-.43-1,3.29,3.29,0,0,0-1.39-.62,3.8,3.8,0,0,1-1.82-.89,2.36,2.36,0,0,1-.52-1.63A2.32,2.32,0,0,1,127.55,7a2.79,2.79,0,0,1,1.94-.72,4.43,4.43,0,0,1,1.18.15,3.54,3.54,0,0,1,1,.44c-.12.22-.23.42-.3.58s-.17.38-.26.62"/>\n      <path class="cls-2" d="M136.44,15.11a3.78,3.78,0,0,1-2.91-1.2,4.45,4.45,0,0,1-1.11-3.14,4.7,4.7,0,0,1,1.09-3.23,3.6,3.6,0,0,1,2.84-1.23h0a3.52,3.52,0,0,1,2.71,1A3.92,3.92,0,0,1,140,9.77c0,.2,0,.41,0,.62l0,.48h0c-.26,0-.68-.08-1.26-.11s-1.16,0-1.75,0h-3v.33a3.84,3.84,0,0,0,.75,2.53,2.61,2.61,0,0,0,2.12.89,3.55,3.55,0,0,0,1.52-.33,4.05,4.05,0,0,0,1.31-1l.15.2q-.06.23-.09.39t-.06.39a5.49,5.49,0,0,1-1.5.73,6.17,6.17,0,0,1-1.75.24M138.39,10V9.62a3.09,3.09,0,0,0-.57-1.94,1.81,1.81,0,0,0-1.5-.74,1.89,1.89,0,0,0-1.74,1,5.09,5.09,0,0,0-.55,2Z"/>\n      <path class="cls-2" d="M140.73,8c0-.47,0-.8,0-1a5.09,5.09,0,0,0-.07-.52,4.58,4.58,0,0,0,.78.06,4.38,4.38,0,0,0,.77-.06c0,.12,0,.28-.08.48s-.05.55-.08,1v.22a4.88,4.88,0,0,1,.43-.65,3.43,3.43,0,0,1,5.19-.14,4.37,4.37,0,0,1,1,3,5.19,5.19,0,0,1-1.08,3.42,3.52,3.52,0,0,1-2.84,1.31,3,3,0,0,1-2.43-1.19l-.11-.14,0,3.26c0,.47,0,.8,0,1a3.4,3.4,0,0,0,.06.52,6.78,6.78,0,0,0-.83,0,6.93,6.93,0,0,0-.82,0,5.09,5.09,0,0,0,.07-.52c0-.2,0-.53,0-1,0-1.3,0-2.81,0-4.53s0-3.21,0-4.51m3.76,6.37a2.08,2.08,0,0,0,1.86-1A5.06,5.06,0,0,0,147,10.6,4.76,4.76,0,0,0,146.37,8a2,2,0,0,0-1.74-.92,2.07,2.07,0,0,0-1.86,1,5.21,5.21,0,0,0-.63,2.83h0a4.74,4.74,0,0,0,.61,2.6A2,2,0,0,0,144.49,14.37Z"/>\n      <path class="cls-2" d="M149.39,13.41c0-1.46.05-3.16.05-5.1s0-3.61-.05-5.07c0-.49,0-.84,0-1.05s0-.36-.06-.47a4.92,4.92,0,0,0,.8.06,5,5,0,0,0,.81-.06,8.29,8.29,0,0,0-.15,1.34c0,.51,0,1.33,0,2.46v2.4a4.78,4.78,0,0,1,.51-.64,3.09,3.09,0,0,1,2.33-1,2.73,2.73,0,0,1,2.08.81,3,3,0,0,1,.77,2.18v4.11c0,.28,0,.51,0,.71s.05.47.1.81c-.25,0-.52,0-.82,0s-.58,0-.82,0a5.09,5.09,0,0,0,.07-.52c0-.2,0-.53,0-1,0-.81,0-1.71,0-2.71V9.87A3.15,3.15,0,0,0,154.5,8,1.74,1.74,0,0,0,153,7.26a2,2,0,0,0-1.68.71,3.33,3.33,0,0,0-.56,2.12l0,3.32c0,.43,0,.74,0,.95a5,5,0,0,0,.06.57c-.24,0-.52,0-.83,0s-.58,0-.82,0q0-.18.06-.48c0-.2,0-.55,0-1"/>\n      <path class="cls-2" d="M157.89,7.21l1.22-3.87.08-.21a1.05,1.05,0,0,1,.45-.53.58.58,0,0,1,.57,0,.63.63,0,0,1,.38.42,1.15,1.15,0,0,1-.11.7l-.11.19L158.28,7.4l-.39-.19"/>\n      <path class="cls-2" d="M165.54,8.1a2,2,0,0,0-.69-.87,1.68,1.68,0,0,0-1-.31,1.42,1.42,0,0,0-1.05.41,1.39,1.39,0,0,0-.41,1.05,1.26,1.26,0,0,0,.42,1,3.25,3.25,0,0,0,1.37.62,4.24,4.24,0,0,1,1.81.83,2,2,0,0,1,.52,1.44,2.63,2.63,0,0,1-.9,2,3.09,3.09,0,0,1-2.19.83,5,5,0,0,1-1.36-.16,2.4,2.4,0,0,1-1-.47c.11-.24.2-.45.27-.62s.14-.39.22-.64a2.48,2.48,0,0,0,.86.95,2.28,2.28,0,0,0,1.19.32,1.79,1.79,0,0,0,1.26-.44,1.47,1.47,0,0,0,.49-1.14,1.24,1.24,0,0,0-.42-1,3.35,3.35,0,0,0-1.39-.62,3.76,3.76,0,0,1-1.82-.89,2.31,2.31,0,0,1-.52-1.63A2.28,2.28,0,0,1,162,7,2.76,2.76,0,0,1,164,6.31a4.49,4.49,0,0,1,1.18.15,3.54,3.54,0,0,1,1,.44,5.48,5.48,0,0,0-.3.58,5.54,5.54,0,0,0-.26.62"/>\n    </g>\n    <path class="cls-3" d="M14.47,15.35a.76.76,0,0,0-.54-.13h0a.67.67,0,0,1-.62-.23,3.1,3.1,0,0,1-.18-1.35V5a2.18,2.18,0,0,0,0-.25,2.62,2.62,0,0,1,.13-1.2c.1-.14.36-.13.57-.12h.14c.52,0,.58-.33.58-.48a.4.4,0,0,0-.11-.29.55.55,0,0,0-.45-.08H11.76a.56.56,0,0,0-.63.37L7.44,12.47C6.85,10.8,4.18,3.3,4.18,3.31a1.55,1.55,0,0,0,0-.15c-.08-.29-.17-.58-.56-.58H1.32a.55.55,0,0,0-.45.08A.4.4,0,0,0,.76,3c0,.15.06.48.57.48s.69,0,.8.14.11.4.08.95l-.58,9.21c-.06,1.11-.12,1.49-1,1.49-.53,0-.61.25-.61.4s.07.38.43.38.55,0,.82,0,.55,0,.83,0,.55,0,.82,0l.84,0c.17,0,.54,0,.54-.38a.35.35,0,0,0-.1-.26.84.84,0,0,0-.57-.14h0a1,1,0,0,1-.81-.28c-.35-.36-.34-1.08-.29-2L3,4.73,6.55,15h0c0,.17.12.49.4.49s.32-.24.38-.41l0-.06,4-10.55v9.18c0,.37,0,1-.24,1.27a1.29,1.29,0,0,1-.78.27h-.06a.76.76,0,0,0-.54.13.37.37,0,0,0-.11.27c0,.18.09.38.48.38s.74,0,1.1,0,.74,0,1.11,0,.6,0,.89,0,.6,0,.9,0,.48-.2.48-.38a.37.37,0,0,0-.11-.27"/>\n    <path class="cls-4" d="M14.47,15.35a.76.76,0,0,0-.54-.13h0a.67.67,0,0,1-.62-.23,3.1,3.1,0,0,1-.18-1.35V5a2.18,2.18,0,0,0,0-.25,2.62,2.62,0,0,1,.13-1.2c.1-.14.36-.13.57-.12h.14c.52,0,.58-.33.58-.48a.4.4,0,0,0-.11-.29.55.55,0,0,0-.45-.08H11.76a.56.56,0,0,0-.63.37L7.44,12.47C6.85,10.8,4.18,3.3,4.18,3.31a1.55,1.55,0,0,0,0-.15c-.08-.29-.17-.58-.56-.58H1.32a.55.55,0,0,0-.45.08A.4.4,0,0,0,.76,3c0,.15.06.48.57.48s.69,0,.8.14.11.4.08.95l-.58,9.21c-.06,1.11-.12,1.49-1,1.49-.53,0-.61.25-.61.4s.07.38.43.38.55,0,.82,0,.55,0,.83,0,.55,0,.82,0l.84,0c.17,0,.54,0,.54-.38a.35.35,0,0,0-.1-.26.84.84,0,0,0-.57-.14h0a1,1,0,0,1-.81-.28c-.35-.36-.34-1.08-.29-2L3,4.73,6.55,15h0c0,.17.12.49.4.49s.32-.24.38-.41l0-.06,4-10.55v9.18c0,.37,0,1-.24,1.27a1.29,1.29,0,0,1-.78.27h-.06a.76.76,0,0,0-.54.13.37.37,0,0,0-.11.27c0,.18.09.38.48.38s.74,0,1.1,0,.74,0,1.11,0,.6,0,.89,0,.6,0,.9,0,.48-.2.48-.38A.37.37,0,0,0,14.47,15.35Z"/>\n    <path class="cls-3" d="M21.61,9c-.32,0-.53-.38-.8-.86-.38-.68-.86-1.52-1.76-1.52a3.14,3.14,0,0,0-1.89.85,4.83,4.83,0,0,0-1.36,3.42c0,2.08,1.35,4.33,3.52,4.33a2.9,2.9,0,0,0,2.16-.91l0,0c.12-.14.23-.25.36-.25a.28.28,0,0,1,.26.3c0,.12-.06.34-.62.87a4.34,4.34,0,0,1-2.93,1.11,4.81,4.81,0,0,1-4.49-5,5.34,5.34,0,0,1,5.19-5.35,4.54,4.54,0,0,1,2.49.74c.26.2.23.57.21.87v.3c0,.39,0,.83-.15,1a.27.27,0,0,1-.22.1"/>\n    <path class="cls-4" d="M21.61,9c-.32,0-.53-.38-.8-.86-.38-.68-.86-1.52-1.76-1.52a3.14,3.14,0,0,0-1.89.85,4.83,4.83,0,0,0-1.36,3.42c0,2.08,1.35,4.33,3.52,4.33a2.9,2.9,0,0,0,2.16-.91l0,0c.12-.14.23-.25.36-.25a.28.28,0,0,1,.26.3c0,.12-.06.34-.62.87a4.34,4.34,0,0,1-2.93,1.11,4.81,4.81,0,0,1-4.49-5,5.34,5.34,0,0,1,5.19-5.35,4.54,4.54,0,0,1,2.49.74c.26.2.23.57.21.87v.3c0,.39,0,.83-.15,1A.27.27,0,0,1,21.61,9Z"/>\n    <path class="cls-3" d="M36.59,15.35a.78.78,0,0,0-.54-.13H36a.68.68,0,0,1-.62-.23,3.26,3.26,0,0,1-.18-1.35V4.75a2.62,2.62,0,0,1,.13-1.2c.09-.14.36-.13.57-.12H36c.51,0,.57-.33.57-.48a.4.4,0,0,0-.11-.29A.55.55,0,0,0,36,2.58H33.87a.55.55,0,0,0-.62.37l-3.7,9.52C29,10.8,26.3,3.3,26.3,3.31a1.31,1.31,0,0,0-.05-.15c-.08-.29-.16-.58-.56-.58H23.43a.55.55,0,0,0-.45.08.4.4,0,0,0-.11.29c0,.15.06.48.58.48s.68,0,.79.14.12.4.08.95l-.57,9.21c-.06,1.11-.13,1.49-1,1.49-.54,0-.62.25-.62.4s.08.38.43.38.55,0,.82,0,.55,0,.83,0,.55,0,.83,0,.56,0,.84,0,.54,0,.54-.38a.36.36,0,0,0-.11-.26.82.82,0,0,0-.56-.14h0a1,1,0,0,1-.81-.28c-.35-.36-.33-1.08-.28-2l.51-8.23L28.66,15h0c0,.17.12.49.4.49s.32-.24.37-.41l0-.06,4-10.55v9.18c0,.37,0,1-.24,1.27a1.25,1.25,0,0,1-.78.27h-.06a.76.76,0,0,0-.54.13.36.36,0,0,0-.1.27c0,.18.08.38.48.38s.73,0,1.09,0,.75,0,1.12,0,.59,0,.88,0l.9,0c.4,0,.48-.2.48-.38a.36.36,0,0,0-.1-.27"/>\n    <path class="cls-4" d="M36.59,15.35a.78.78,0,0,0-.54-.13H36a.68.68,0,0,1-.62-.23,3.26,3.26,0,0,1-.18-1.35V4.75a2.62,2.62,0,0,1,.13-1.2c.09-.14.36-.13.57-.12H36c.51,0,.57-.33.57-.48a.4.4,0,0,0-.11-.29A.55.55,0,0,0,36,2.58H33.87a.55.55,0,0,0-.62.37l-3.7,9.52C29,10.8,26.3,3.3,26.3,3.31a1.31,1.31,0,0,0-.05-.15c-.08-.29-.16-.58-.56-.58H23.43a.55.55,0,0,0-.45.08.4.4,0,0,0-.11.29c0,.15.06.48.58.48s.68,0,.79.14.12.4.08.95l-.57,9.21c-.06,1.11-.13,1.49-1,1.49-.54,0-.62.25-.62.4s.08.38.43.38.55,0,.82,0,.55,0,.83,0,.55,0,.83,0,.56,0,.84,0,.54,0,.54-.38a.36.36,0,0,0-.11-.26.82.82,0,0,0-.56-.14h0a1,1,0,0,1-.81-.28c-.35-.36-.33-1.08-.28-2l.51-8.23L28.66,15h0c0,.17.12.49.4.49s.32-.24.37-.41l0-.06,4-10.55v9.18c0,.37,0,1-.24,1.27a1.25,1.25,0,0,1-.78.27h-.06a.76.76,0,0,0-.54.13.36.36,0,0,0-.1.27c0,.18.08.38.48.38s.73,0,1.09,0,.75,0,1.12,0,.59,0,.88,0l.9,0c.4,0,.48-.2.48-.38A.36.36,0,0,0,36.59,15.35Z"/>\n    <path class="cls-3" d="M41,10.49c.66-.34.66-.34.66-1.1v-1c0-1.13-.08-1.82-1.14-1.82s-1.64.5-2.14,1.74l0,.1a1.29,1.29,0,0,1-.57.75,2.39,2.39,0,0,1-.89.29c-.26,0-.38-.13-.38-.39a2.55,2.55,0,0,1,.85-1.63A5.34,5.34,0,0,1,41,5.94a2.53,2.53,0,0,1,1.87.61A1.72,1.72,0,0,1,43.3,8v5.37c0,.34,0,1.16.3,1.46a.34.34,0,0,0,.26.1.77.77,0,0,0,.55-.33c.11-.11.2-.21.33-.21a.29.29,0,0,1,.26.3c0,.29-.32.59-.49.75l0,0a2.58,2.58,0,0,1-1.48.66c-.7,0-1-.7-1.18-1.17a1.41,1.41,0,0,0-.17-.35h.06a1.66,1.66,0,0,0-.26.22,4.69,4.69,0,0,1-2.94,1.43,1.86,1.86,0,0,1-2-1.84c0-1.55,1.7-2.47,2.83-3.08l.13-.07L41,10.49m-1.3,1.44c-.76.44-1.47,1-1.47,1.93A1.12,1.12,0,0,0,39.5,15a2.42,2.42,0,0,0,1.74-.83,1.88,1.88,0,0,0,.46-1.54V11.28c0-.33,0-.4,0-.42h0l-.09,0-.08,0h0l-1.79,1"/>\n    <path class="cls-4" d="M41,10.49c.66-.34.66-.34.66-1.1v-1c0-1.13-.08-1.82-1.14-1.82s-1.64.5-2.14,1.74l0,.1a1.29,1.29,0,0,1-.57.75,2.39,2.39,0,0,1-.89.29c-.26,0-.38-.13-.38-.39a2.55,2.55,0,0,1,.85-1.63A5.34,5.34,0,0,1,41,5.94a2.53,2.53,0,0,1,1.87.61A1.72,1.72,0,0,1,43.3,8v5.37c0,.34,0,1.16.3,1.46a.34.34,0,0,0,.26.1.77.77,0,0,0,.55-.33c.11-.11.2-.21.33-.21a.29.29,0,0,1,.26.3c0,.29-.32.59-.49.75l0,0a2.58,2.58,0,0,1-1.48.66c-.7,0-1-.7-1.18-1.17a1.41,1.41,0,0,0-.17-.35h.06a1.66,1.66,0,0,0-.26.22,4.69,4.69,0,0,1-2.94,1.43,1.86,1.86,0,0,1-2-1.84c0-1.55,1.7-2.47,2.83-3.08l.13-.07Zm-1.3,1.44c-.76.44-1.47,1-1.47,1.93A1.12,1.12,0,0,0,39.5,15a2.42,2.42,0,0,0,1.74-.83,1.88,1.88,0,0,0,.46-1.54V11.28c0-.33,0-.4,0-.42h0l-.09,0-.08,0h0Z"/>\n    <path class="cls-3" d="M45.38,13.23v0c0-.19.06-.57.38-.57s.42.42.52.91c.16.87.39,2.07,2.05,2.07a2.11,2.11,0,0,0,2.26-2c0-1.2-.93-1.64-1.8-2l-.17-.06c-1.23-.44-2.91-1-2.91-2.8a2.65,2.65,0,0,1,1.09-2.12,3.74,3.74,0,0,1,2.39-.73,6.78,6.78,0,0,1,2.07.36c.35.19.32.58.3.9a1.41,1.41,0,0,0,0,.2.46.46,0,0,0,0,.1c0,.39,0,.81-.13,1a.25.25,0,0,1-.2.09c-.25,0-.35-.25-.48-.58a1.85,1.85,0,0,0-1.91-1.46A1.65,1.65,0,0,0,47.17,8c0,1.08,1,1.44,2.06,1.85,1.33.51,2.83,1.07,2.83,3.08,0,2.28-2.24,3.3-3.84,3.3a6.22,6.22,0,0,1-2.56-.67c-.34-.17-.34-.48-.34-.79v-.1l.06-1.47"/>\n    <path class="cls-4" d="M45.38,13.23v0c0-.19.06-.57.38-.57s.42.42.52.91c.16.87.39,2.07,2.05,2.07a2.11,2.11,0,0,0,2.26-2c0-1.2-.93-1.64-1.8-2l-.17-.06c-1.23-.44-2.91-1-2.91-2.8a2.65,2.65,0,0,1,1.09-2.12,3.74,3.74,0,0,1,2.39-.73,6.78,6.78,0,0,1,2.07.36c.35.19.32.58.3.9a1.41,1.41,0,0,0,0,.2.46.46,0,0,0,0,.1c0,.39,0,.81-.13,1a.25.25,0,0,1-.2.09c-.25,0-.35-.25-.48-.58a1.85,1.85,0,0,0-1.91-1.46A1.65,1.65,0,0,0,47.17,8c0,1.08,1,1.44,2.06,1.85,1.33.51,2.83,1.07,2.83,3.08,0,2.28-2.24,3.3-3.84,3.3a6.22,6.22,0,0,1-2.56-.67c-.34-.17-.34-.48-.34-.79v-.1Z"/>\n    <path class="cls-3" d="M57.53,14.7a.28.28,0,0,0-.26-.28c-.1,0-.19.08-.34.22a1.77,1.77,0,0,1-1.07.54.78.78,0,0,1-.58-.22,3.43,3.43,0,0,1-.44-2.15V7.26c0-.22,0-.3.06-.33a.57.57,0,0,1,.32,0h1.52c.17,0,.31,0,.41-.08a.51.51,0,0,0,.11-.39c0-.16,0-.43-.3-.43H55c-.16,0-.19,0-.19-.31V4.16c0-.32-.16-.39-.29-.39s-.28.2-.31.28a4.73,4.73,0,0,1-1.83,2.14l0,0a.49.49,0,0,0-.23.38.28.28,0,0,0,.08.2.78.78,0,0,0,.59.1H53a.5.5,0,0,1,.2,0,.65.65,0,0,1,0,.25v5.91a4.16,4.16,0,0,0,.46,2.46,1.85,1.85,0,0,0,1.51.72,2.68,2.68,0,0,0,1.9-.85,1.17,1.17,0,0,0,.43-.71"/>\n    <path class="cls-4" d="M57.53,14.7a.28.28,0,0,0-.26-.28c-.1,0-.19.08-.34.22a1.77,1.77,0,0,1-1.07.54.78.78,0,0,1-.58-.22,3.43,3.43,0,0,1-.44-2.15V7.26c0-.22,0-.3.06-.33a.57.57,0,0,1,.32,0h1.52c.17,0,.31,0,.41-.08a.51.51,0,0,0,.11-.39c0-.16,0-.43-.3-.43H55c-.16,0-.19,0-.19-.31V4.16c0-.32-.16-.39-.29-.39s-.28.2-.31.28a4.73,4.73,0,0,1-1.83,2.14l0,0a.49.49,0,0,0-.23.38.28.28,0,0,0,.08.2.78.78,0,0,0,.59.1H53a.5.5,0,0,1,.2,0,.65.65,0,0,1,0,.25v5.91a4.16,4.16,0,0,0,.46,2.46,1.85,1.85,0,0,0,1.51.72,2.68,2.68,0,0,0,1.9-.85A1.17,1.17,0,0,0,57.53,14.7Z"/>\n    <path class="cls-3" d="M65.72,13.63c-.13,0-.23.1-.41.29A3.36,3.36,0,0,1,62.82,15c-2.4,0-3.66-2.21-3.66-4.4,0-.27,0-.42.09-.48s.23-.07.48-.07h6c.1,0,.36-.05.36-.5a4.31,4.31,0,0,0-.71-2.26,3.57,3.57,0,0,0-2.92-1.39,5.1,5.1,0,0,0-3.61,1.48,4.77,4.77,0,0,0-1.43,3.71c0,2.88,2,5.13,4.57,5.13A4.35,4.35,0,0,0,65.2,15v0c.55-.52.79-.84.79-1.05a.29.29,0,0,0-.28-.31M59.78,8a2.93,2.93,0,0,1,2.44-1.38,2.1,2.1,0,0,1,1.6.62A2,2,0,0,1,64.3,8.4a.71.71,0,0,1-.63.74,11,11,0,0,1-2.24.17H59.75c-.13,0-.33,0-.4-.06a.1.1,0,0,1,0-.09A3,3,0,0,1,59.78,8"/>\n    <path class="cls-4" d="M65.72,13.63c-.13,0-.23.1-.41.29A3.36,3.36,0,0,1,62.82,15c-2.4,0-3.66-2.21-3.66-4.4,0-.27,0-.42.09-.48s.23-.07.48-.07h6c.1,0,.36-.05.36-.5a4.31,4.31,0,0,0-.71-2.26,3.57,3.57,0,0,0-2.92-1.39,5.1,5.1,0,0,0-3.61,1.48,4.77,4.77,0,0,0-1.43,3.71c0,2.88,2,5.13,4.57,5.13A4.35,4.35,0,0,0,65.2,15v0c.55-.52.79-.84.79-1.05A.29.29,0,0,0,65.72,13.63ZM59.78,8a2.93,2.93,0,0,1,2.44-1.38,2.1,2.1,0,0,1,1.6.62A2,2,0,0,1,64.3,8.4a.71.71,0,0,1-.63.74,11,11,0,0,1-2.24.17H59.75c-.13,0-.33,0-.4-.06a.1.1,0,0,1,0-.09A3,3,0,0,1,59.78,8Z"/>\n    <path class="cls-3" d="M71.69,6.05a2.88,2.88,0,0,0-2.12,1.46l-.16.21V6.36A.49.49,0,0,0,69.32,6a.27.27,0,0,0-.21-.08.52.52,0,0,0-.39.25l-.07.08a4.19,4.19,0,0,1-1.56,1.08l-.08,0c-.17.06-.46.15-.46.46s.15.31.37.31h.25c.23,0,.41,0,.47.13a2.9,2.9,0,0,1,.17,1.23V14c0,.82,0,1.22-.77,1.3h-.1c-.19,0-.56,0-.56.43,0,.22.15.35.4.35s.62,0,.92,0,.63,0,.94,0,.57,0,.88,0,.63,0,1,0a.34.34,0,0,0,.37-.37c0-.37-.38-.39-.58-.41h-.08c-.77-.08-.8-.48-.77-1.3V10.12a3.2,3.2,0,0,1,.43-2c.21-.29.52-.73.89-.73.19,0,.29.13.45.33a1,1,0,0,0,.8.5.93.93,0,0,0,1-1,1.18,1.18,0,0,0-1.24-1.17"/>\n    <path class="cls-4" d="M71.69,6.05a2.88,2.88,0,0,0-2.12,1.46l-.16.21V6.36A.49.49,0,0,0,69.32,6a.27.27,0,0,0-.21-.08.52.52,0,0,0-.39.25l-.07.08a4.19,4.19,0,0,1-1.56,1.08l-.08,0c-.17.06-.46.15-.46.46s.15.31.37.31h.25c.23,0,.41,0,.47.13a2.9,2.9,0,0,1,.17,1.23V14c0,.82,0,1.22-.77,1.3h-.1c-.19,0-.56,0-.56.43,0,.22.15.35.4.35s.62,0,.92,0,.63,0,.94,0,.57,0,.88,0,.63,0,1,0a.34.34,0,0,0,.37-.37c0-.37-.38-.39-.58-.41h-.08c-.77-.08-.8-.48-.77-1.3V10.12a3.2,3.2,0,0,1,.43-2c.21-.29.52-.73.89-.73.19,0,.29.13.45.33a1,1,0,0,0,.8.5.93.93,0,0,0,1-1A1.18,1.18,0,0,0,71.69,6.05Z"/>\n    <path class="cls-3" d="M6.39,20.36v-.07a3.37,3.37,0,0,0-.1-1.12c-.11-.21-.31-.23-.57-.23h0a.41.41,0,0,1-.34-.09.27.27,0,0,1-.08-.2.28.28,0,0,1,.08-.2.39.39,0,0,1,.29-.1,4.41,4.41,0,0,1,.52,0l.5,0,.43,0a3.44,3.44,0,0,1,.46,0c.33,0,.37.2.37.29s-.17.3-.5.3-.44.22-.45.73a1.48,1.48,0,0,1,0,.21v3.94a2.53,2.53,0,0,1-.66,2.1,3.08,3.08,0,0,1-2.23.71A3.65,3.65,0,0,1,1.89,26a2.33,2.33,0,0,1-.72-2.12V19.7c0-.34,0-.56-.09-.65a.78.78,0,0,0-.52-.11c-.27,0-.41-.09-.41-.29a.33.33,0,0,1,.08-.22.36.36,0,0,1,.24-.08c.22,0,.44,0,.65,0l.62,0c.22,0,.44,0,.65,0l.65,0a.28.28,0,0,1,.32.3c0,.2-.14.29-.42.29a.78.78,0,0,0-.52.11c-.09.09-.09.31-.09.65v3.84a4.48,4.48,0,0,0,.22,1.76c.38.7,1.42.76,1.73.76A2.4,2.4,0,0,0,6,25.42a2.1,2.1,0,0,0,.37-1.55V20.36Z"/>\n    <path class="cls-4" d="M6.39,20.36v-.07a3.37,3.37,0,0,0-.1-1.12c-.11-.21-.31-.23-.57-.23h0a.41.41,0,0,1-.34-.09.27.27,0,0,1-.08-.2.28.28,0,0,1,.08-.2.39.39,0,0,1,.29-.1,4.41,4.41,0,0,1,.52,0l.5,0,.43,0a3.44,3.44,0,0,1,.46,0c.33,0,.37.2.37.29s-.17.3-.5.3-.44.22-.45.73a1.48,1.48,0,0,1,0,.21v3.94a2.53,2.53,0,0,1-.66,2.1,3.08,3.08,0,0,1-2.23.71A3.65,3.65,0,0,1,1.89,26a2.33,2.33,0,0,1-.72-2.12V19.7c0-.34,0-.56-.09-.65a.78.78,0,0,0-.52-.11c-.27,0-.41-.09-.41-.29a.33.33,0,0,1,.08-.22.36.36,0,0,1,.24-.08c.22,0,.44,0,.65,0l.62,0c.22,0,.44,0,.65,0l.65,0a.28.28,0,0,1,.32.3c0,.2-.14.29-.42.29a.78.78,0,0,0-.52.11c-.09.09-.09.31-.09.65v3.84a4.48,4.48,0,0,0,.22,1.76c.38.7,1.42.76,1.73.76A2.4,2.4,0,0,0,6,25.42a2.1,2.1,0,0,0,.37-1.55V20.36Z"/>\n    <path class="cls-3" d="M13.88,26h0c-.4,0-.42-.22-.4-.71V23a2.88,2.88,0,0,0-.36-1.72,1.66,1.66,0,0,0-1.45-.73,2.45,2.45,0,0,0-1.66.84l-.07.07v-.6a.35.35,0,0,0-.07-.25.22.22,0,0,0-.16-.06.33.33,0,0,0-.27.17s0,0,0,0a2.4,2.4,0,0,1-.88.62H8.43c-.1,0-.3.1-.3.32a.24.24,0,0,0,.27.23h.15c.13,0,.21,0,.23.06s.08.19.08.68v2.63c0,.48,0,.66-.4.7H8.41c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.18,0,.37,0,.56,0a.26.26,0,0,0,.27-.27c0-.26-.27-.28-.39-.29h-.05c-.39,0-.41-.22-.4-.7a1.48,1.48,0,0,0,0-.21V22.94a1.42,1.42,0,0,1,1.36-1.59,1.09,1.09,0,0,1,1,.51,2.58,2.58,0,0,1,.18,1.19v2.21c0,.49,0,.67-.39.71H12c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.19,0,.37,0,.56,0a.26.26,0,0,0,.27-.27c0-.26-.27-.28-.39-.29"/>\n    <path class="cls-4" d="M13.88,26h0c-.4,0-.42-.22-.4-.71V23a2.88,2.88,0,0,0-.36-1.72,1.66,1.66,0,0,0-1.45-.73,2.45,2.45,0,0,0-1.66.84l-.07.07v-.6a.35.35,0,0,0-.07-.25.22.22,0,0,0-.16-.06.33.33,0,0,0-.27.17s0,0,0,0a2.4,2.4,0,0,1-.88.62H8.43c-.1,0-.3.1-.3.32a.24.24,0,0,0,.27.23h.15c.13,0,.21,0,.23.06s.08.19.08.68v2.63c0,.48,0,.66-.4.7H8.41c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.18,0,.37,0,.56,0a.26.26,0,0,0,.27-.27c0-.26-.27-.28-.39-.29h-.05c-.39,0-.41-.22-.4-.7a1.48,1.48,0,0,0,0-.21V22.94a1.42,1.42,0,0,1,1.36-1.59,1.09,1.09,0,0,1,1,.51,2.58,2.58,0,0,1,.18,1.19v2.21c0,.49,0,.67-.39.71H12c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.19,0,.37,0,.56,0a.26.26,0,0,0,.27-.27C14.27,26,14,26,13.88,26Z"/>\n    <path class="cls-3" d="M15.55,18.93a.7.7,0,0,1,.64-.76.68.68,0,0,1,.61.74c0,.45-.25.76-.63.76a.66.66,0,0,1-.62-.74m1.14,6.13v.21c0,.48,0,.66.4.7h.05c.11,0,.38,0,.38.29a.25.25,0,0,1-.26.27c-.19,0-.38,0-.56,0l-.51,0c-.18,0-.36,0-.53,0l-.54,0a.25.25,0,0,1-.29-.26c0-.28.26-.3.38-.3h0c.4,0,.41-.22.4-.7V22.64c0-.48-.05-.64-.09-.68s-.09-.06-.23-.06h-.15a.23.23,0,0,1-.26-.23c0-.22.2-.28.3-.32h0a2.35,2.35,0,0,0,.89-.62l0,0a.37.37,0,0,1,.27-.17.2.2,0,0,1,.16.06.31.31,0,0,1,.07.25v4.24Z"/>\n    <path class="cls-4" d="M15.55,18.93a.7.7,0,0,1,.64-.76.68.68,0,0,1,.61.74c0,.45-.25.76-.63.76A.66.66,0,0,1,15.55,18.93Zm1.14,6.13v.21c0,.48,0,.66.4.7h.05c.11,0,.38,0,.38.29a.25.25,0,0,1-.26.27c-.19,0-.38,0-.56,0l-.51,0c-.18,0-.36,0-.53,0l-.54,0a.25.25,0,0,1-.29-.26c0-.28.26-.3.38-.3h0c.4,0,.41-.22.4-.7V22.64c0-.48-.05-.64-.09-.68s-.09-.06-.23-.06h-.15a.23.23,0,0,1-.26-.23c0-.22.2-.28.3-.32h0a2.35,2.35,0,0,0,.89-.62l0,0a.37.37,0,0,1,.27-.17.2.2,0,0,1,.16.06.31.31,0,0,1,.07.25v4.24Z"/>\n    <path class="cls-3" d="M23.59,20.72a.22.22,0,0,0-.18,0H21.7c-.08,0-.3,0-.3.24s.33.27.43.27.32,0,.32.21a1.94,1.94,0,0,1-.11.41l0,.09s-.88,2.15-1.22,3l-1-2.86,0,0a2.42,2.42,0,0,1-.16-.55c0-.18.19-.22.3-.22h0a.47.47,0,0,0,.34-.08.21.21,0,0,0,.07-.17.25.25,0,0,0-.07-.19.35.35,0,0,0-.25-.07h-2.1a.29.29,0,0,0-.21.06.25.25,0,0,0-.07.18c0,.18.12.27.34.27s.41.15.56.56l0,.09,1.65,4.43.07.16a.24.24,0,0,0,.22.21c.16,0,.24-.19.29-.32v0h0l1.63-3.92a1.34,1.34,0,0,0,.07-.18c.17-.44.37-.93.76-1h0c.1,0,.37,0,.37-.28a.22.22,0,0,0-.06-.17"/>\n    <path class="cls-4" d="M23.59,20.72a.22.22,0,0,0-.18,0H21.7c-.08,0-.3,0-.3.24s.33.27.43.27.32,0,.32.21a1.94,1.94,0,0,1-.11.41l0,.09s-.88,2.15-1.22,3l-1-2.86,0,0a2.42,2.42,0,0,1-.16-.55c0-.18.19-.22.3-.22h0a.47.47,0,0,0,.34-.08.21.21,0,0,0,.07-.17.25.25,0,0,0-.07-.19.35.35,0,0,0-.25-.07h-2.1a.29.29,0,0,0-.21.06.25.25,0,0,0-.07.18c0,.18.12.27.34.27s.41.15.56.56l0,.09,1.65,4.43.07.16a.24.24,0,0,0,.22.21c.16,0,.24-.19.29-.32v0h0l1.63-3.92a1.34,1.34,0,0,0,.07-.18c.17-.44.37-.93.76-1h0c.1,0,.37,0,.37-.28A.22.22,0,0,0,23.59,20.72Z"/>\n    <path class="cls-3" d="M28.57,25c-.1,0-.17.07-.28.18a1.87,1.87,0,0,1-1.41.64,2.27,2.27,0,0,1-2.07-2.52c0-.18,0-.23,0-.24a.66.66,0,0,1,.24,0h3.5c.06,0,.26,0,.26-.35a2.47,2.47,0,0,0-.42-1.34,2.12,2.12,0,0,0-1.74-.84,3,3,0,0,0-2.13.88,2.79,2.79,0,0,0-.86,2.2,2.86,2.86,0,0,0,2.72,3,2.59,2.59,0,0,0,1.89-.74c.42-.4.48-.56.48-.66a.22.22,0,0,0-.22-.23m-3.41-3.22A1.65,1.65,0,0,1,26.53,21a1.16,1.16,0,0,1,.89.34,1.12,1.12,0,0,1,.27.66c0,.21-.1.32-.33.38a6.71,6.71,0,0,1-1.28.1h-1a.65.65,0,0,1-.2,0v0a1.69,1.69,0,0,1,.26-.66"/>\n    <path class="cls-4" d="M28.57,25c-.1,0-.17.07-.28.18a1.87,1.87,0,0,1-1.41.64,2.27,2.27,0,0,1-2.07-2.52c0-.18,0-.23,0-.24a.66.66,0,0,1,.24,0h3.5c.06,0,.26,0,.26-.35a2.47,2.47,0,0,0-.42-1.34,2.12,2.12,0,0,0-1.74-.84,3,3,0,0,0-2.13.88,2.79,2.79,0,0,0-.86,2.2,2.86,2.86,0,0,0,2.72,3,2.59,2.59,0,0,0,1.89-.74c.42-.4.48-.56.48-.66A.22.22,0,0,0,28.57,25Zm-3.41-3.22A1.65,1.65,0,0,1,26.53,21a1.16,1.16,0,0,1,.89.34,1.12,1.12,0,0,1,.27.66c0,.21-.1.32-.33.38a6.71,6.71,0,0,1-1.28.1h-1a.65.65,0,0,1-.2,0v0A1.69,1.69,0,0,1,25.16,21.78Z"/>\n    <path class="cls-3" d="M32.63,20.58a1.7,1.7,0,0,0-1.27.87v-.63a.33.33,0,0,0-.07-.25.22.22,0,0,0-.16-.06.33.33,0,0,0-.27.17s0,0,0,0a2.4,2.4,0,0,1-.88.62h0c-.11,0-.31.1-.31.32a.24.24,0,0,0,.27.23H30c.13,0,.21,0,.23.06s.08.19.08.68v2.63c0,.48,0,.66-.39.7h-.06c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.18,0,.37,0,.56,0a.26.26,0,0,0,.27-.27c0-.26-.27-.28-.39-.29h-.05c-.39,0-.41-.22-.39-.7V23a1.8,1.8,0,0,1,.24-1.13c.11-.15.28-.4.47-.4s.14.07.22.18a.62.62,0,0,0,.51.3.59.59,0,0,0,.6-.63.74.74,0,0,0-.77-.74"/>\n    <path class="cls-4" d="M32.63,20.58a1.7,1.7,0,0,0-1.27.87v-.63a.33.33,0,0,0-.07-.25.22.22,0,0,0-.16-.06.33.33,0,0,0-.27.17s0,0,0,0a2.4,2.4,0,0,1-.88.62h0c-.11,0-.31.1-.31.32a.24.24,0,0,0,.27.23H30c.13,0,.21,0,.23.06s.08.19.08.68v2.63c0,.48,0,.66-.39.7h-.06c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.18,0,.37,0,.56,0a.26.26,0,0,0,.27-.27c0-.26-.27-.28-.39-.29h-.05c-.39,0-.41-.22-.39-.7V23a1.8,1.8,0,0,1,.24-1.13c.11-.15.28-.4.47-.4s.14.07.22.18a.62.62,0,0,0,.51.3.59.59,0,0,0,.6-.63A.74.74,0,0,0,32.63,20.58Z"/>\n    <path class="cls-3" d="M33.88,24.81v0c0-.11,0-.38.27-.38s.3.28.36.57c.09.52.22,1.16,1.13,1.16A1.17,1.17,0,0,0,36.9,25c0-.6-.38-.87-1-1.1l-.1,0c-.72-.26-1.72-.61-1.72-1.68A1.59,1.59,0,0,1,34.72,21a2.17,2.17,0,0,1,1.42-.44,4.09,4.09,0,0,1,1.23.22c.24.13.22.39.21.58s0,.08,0,.11a.43.43,0,0,1,0,0,.9.9,0,0,1-.09.63.24.24,0,0,1-.16.07c-.18,0-.25-.18-.33-.38A1,1,0,0,0,35.94,21a.9.9,0,0,0-.92.81c0,.59.54.79,1.16,1,.79.29,1.69.63,1.69,1.84a2.14,2.14,0,0,1-2.3,2,3.58,3.58,0,0,1-1.5-.4c-.23-.11-.23-.32-.23-.5v-.06s0-.86,0-.86"/>\n    <path class="cls-4" d="M33.88,24.81v0c0-.11,0-.38.27-.38s.3.28.36.57c.09.52.22,1.16,1.13,1.16A1.17,1.17,0,0,0,36.9,25c0-.6-.38-.87-1-1.1l-.1,0c-.72-.26-1.72-.61-1.72-1.68A1.59,1.59,0,0,1,34.72,21a2.17,2.17,0,0,1,1.42-.44,4.09,4.09,0,0,1,1.23.22c.24.13.22.39.21.58s0,.08,0,.11a.43.43,0,0,1,0,0,.9.9,0,0,1-.09.63.24.24,0,0,1-.16.07c-.18,0-.25-.18-.33-.38A1,1,0,0,0,35.94,21a.9.9,0,0,0-.92.81c0,.59.54.79,1.16,1,.79.29,1.69.63,1.69,1.84a2.14,2.14,0,0,1-2.3,2,3.58,3.58,0,0,1-1.5-.4c-.23-.11-.23-.32-.23-.5v-.06S33.88,24.81,33.88,24.81Z"/>\n    <path class="cls-3" d="M40,19.67c.38,0,.63-.31.63-.76a.68.68,0,0,0-.6-.74.7.7,0,0,0-.64.76.66.66,0,0,0,.61.74"/>\n    <path class="cls-4" d="M40,19.67c.38,0,.63-.31.63-.76a.68.68,0,0,0-.6-.74.7.7,0,0,0-.64.76A.66.66,0,0,0,40,19.67Z"/>\n    <path class="cls-3" d="M41,26h0c-.39,0-.41-.22-.39-.7V20.82a.35.35,0,0,0-.07-.25.22.22,0,0,0-.16-.06.33.33,0,0,0-.27.17l0,0a2.4,2.4,0,0,1-.88.62h0c-.1,0-.3.1-.3.32a.24.24,0,0,0,.27.23h.15c.13,0,.21,0,.23.06s.08.19.08.68v2.63c0,.48,0,.66-.39.7h-.06c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.18,0,.37,0,.56,0a.26.26,0,0,0,.27-.27c0-.26-.27-.28-.39-.29"/>\n    <path class="cls-4" d="M41,26h0c-.39,0-.41-.22-.39-.7V20.82a.35.35,0,0,0-.07-.25.22.22,0,0,0-.16-.06.33.33,0,0,0-.27.17l0,0a2.4,2.4,0,0,1-.88.62h0c-.1,0-.3.1-.3.32a.24.24,0,0,0,.27.23h.15c.13,0,.21,0,.23.06s.08.19.08.68v2.63c0,.48,0,.66-.39.7h-.06c-.11,0-.38,0-.38.3a.26.26,0,0,0,.29.26c.18,0,.36,0,.54,0s.36,0,.54,0l.5,0c.18,0,.37,0,.56,0a.26.26,0,0,0,.27-.27C41.4,26,41.13,26,41,26Z"/>\n    <path class="cls-3" d="M44.81,25.67a.23.23,0,0,0-.21-.22c-.08,0-.14.05-.24.14a1,1,0,0,1-.58.3.4.4,0,0,1-.3-.11c-.24-.24-.24-.83-.24-1.22V21.33c0-.13,0-.15,0-.15h1a.34.34,0,0,0,.28-.06.36.36,0,0,0,.08-.27c0-.08,0-.31-.23-.31,0,0-1.13,0-1.12,0h0a.68.68,0,0,1,0-.12v-.89c0-.26-.16-.28-.22-.28a.26.26,0,0,0-.23.19,2.66,2.66,0,0,1-1,1.22l0,0a.37.37,0,0,0-.16.27.24.24,0,0,0,.07.16.56.56,0,0,0,.39.07h.17a.28.28,0,0,1,0,.11v3.44a2.53,2.53,0,0,0,.27,1.47,1.14,1.14,0,0,0,.92.44,1.6,1.6,0,0,0,1.14-.51.67.67,0,0,0,.28-.45"/>\n    <path class="cls-4" d="M44.81,25.67a.23.23,0,0,0-.21-.22c-.08,0-.14.05-.24.14a1,1,0,0,1-.58.3.4.4,0,0,1-.3-.11c-.24-.24-.24-.83-.24-1.22V21.33c0-.13,0-.15,0-.15h1a.34.34,0,0,0,.28-.06.36.36,0,0,0,.08-.27c0-.08,0-.31-.23-.31,0,0-1.13,0-1.12,0h0a.68.68,0,0,1,0-.12v-.89c0-.26-.16-.28-.22-.28a.26.26,0,0,0-.23.19,2.66,2.66,0,0,1-1,1.22l0,0a.37.37,0,0,0-.16.27.24.24,0,0,0,.07.16.56.56,0,0,0,.39.07h.17a.28.28,0,0,1,0,.11v3.44a2.53,2.53,0,0,0,.27,1.47,1.14,1.14,0,0,0,.92.44,1.6,1.6,0,0,0,1.14-.51A.67.67,0,0,0,44.81,25.67Z"/>\n    <path class="cls-3" d="M50.8,20.67H49a.29.29,0,0,0-.29.29c0,.22.27.22.39.22.31,0,.47.11.47.32a1.42,1.42,0,0,1-.14.46v0l-1.15,3c-.31-.85-1.15-3.07-1.15-3.07v0a1.53,1.53,0,0,1-.12-.44c0-.25.41-.25.45-.25.27,0,.41-.08.41-.22a.28.28,0,0,0-.29-.29H45.37c-.21,0-.35.12-.35.29s.28.22.4.22c.28,0,.4.26.55.67L46,22l1.49,3.94a.78.78,0,0,1,.05.14,1.13,1.13,0,0,1,.11.36.63.63,0,0,1-.07.26l0,.08-.38,1,0,.09c0,.15-.09.26-.18.28a1.18,1.18,0,0,1-.38,0H46.5c-.49,0-.49.44-.49.63a.52.52,0,0,0,.13.38.88.88,0,0,0,.61.15h0c.5,0,.56-.13.68-.57,0,0,0,0,0,0l2.28-6a8.09,8.09,0,0,1,.61-1.33.75.75,0,0,1,.4-.24h.06c.11,0,.3,0,.3-.2a.28.28,0,0,0-.3-.3"/>\n    <path class="cls-4" d="M50.8,20.67H49a.29.29,0,0,0-.29.29c0,.22.27.22.39.22.31,0,.47.11.47.32a1.42,1.42,0,0,1-.14.46v0l-1.15,3c-.31-.85-1.15-3.07-1.15-3.07v0a1.53,1.53,0,0,1-.12-.44c0-.25.41-.25.45-.25.27,0,.41-.08.41-.22a.28.28,0,0,0-.29-.29H45.37c-.21,0-.35.12-.35.29s.28.22.4.22c.28,0,.4.26.55.67L46,22l1.49,3.94a.78.78,0,0,1,.05.14,1.13,1.13,0,0,1,.11.36.63.63,0,0,1-.07.26l0,.08-.38,1,0,.09c0,.15-.09.26-.18.28a1.18,1.18,0,0,1-.38,0H46.5c-.49,0-.49.44-.49.63a.52.52,0,0,0,.13.38.88.88,0,0,0,.61.15h0c.5,0,.56-.13.68-.57,0,0,0,0,0,0l2.28-6a8.09,8.09,0,0,1,.61-1.33.75.75,0,0,1,.4-.24h.06c.11,0,.3,0,.3-.2A.28.28,0,0,0,50.8,20.67Z"/>\n    <g>\n      <path class="cls-5" d="M63,42.89c-5.63-1.74-9-7.38-9.33-10.79,0,0,0-.06,0-13.31v-1H72.83V32c-.3,3.45-3.7,9.14-9.32,10.87l-.27.07Z"/>\n      <path class="cls-3" d="M72.26,18.31H54.09V32.06c.29,3.27,3.58,8.7,9,10.38l.08,0h.12l.08,0c5.42-1.68,8.7-7.13,9-10.42V18.31Z"/>\n      <path class="cls-6" d="M63.26,20.18h3V23H63.81a.58.58,0,0,0-1.1,0H60.23V20.18h3"/>\n      <path class="cls-7" d="M63.2,23.73h8.67V32c-.24,2.85-3.21,8.28-8.64,10-5.43-1.68-8.41-7.11-8.66-10V23.73H63.2Z"/>\n      <path class="cls-7" d="M57.44,23h.21a.32.32,0,0,1-.19-.31,1.68,1.68,0,0,1,.06-.56l.75.07-.15-.24.78-.74-.21-.07.14-.53-.49.11-.09-.25-.34.39.09-.91-.28.23-.33-.64h0l-.33.64-.28-.23.09.91-.34-.39-.08.25L56,20.58l.13.53-.21.07.78.74-.15.24.76-.07a1.68,1.68,0,0,1,.06.56.38.38,0,0,1-.19.31Z"/>\n      <path class="cls-7" d="M69,23h-.22a.34.34,0,0,0,.2-.31,1.84,1.84,0,0,0-.07-.56l-.75.07.15-.24-.78-.74.21-.07-.13-.53.48.11.09-.25.34.39-.09-.91.28.23.33-.64h0l.33.64.28-.23-.09.91.34-.39.09.25.48-.11-.13.53.21.07-.78.74.15.24-.75-.07a1.68,1.68,0,0,0-.06.56.34.34,0,0,0,.19.31Z"/>\n      <path class="cls-7" d="M63.26,22.35c.34-.36,1.29.21,1.61.24.15,0,.91,0,.91,0V19.74h-.37a2.4,2.4,0,0,1-.82-.09c-.27-.11-1-.37-1.33.14-.34-.51-1.06-.25-1.34-.14a2.33,2.33,0,0,1-.81.09h-.37V22.6s.76,0,.91,0C62,22.56,62.92,22,63.26,22.35Z"/>\n      <path class="cls-6" d="M63.16,22.28l.1.07.09-.07V19.67a1.25,1.25,0,0,0-.09.12.4.4,0,0,0-.1-.12Z"/>\n      <path class="cls-6" d="M62.05,27.28s.87.06.94-.69c0,0,.07.56.25.57s.19-.59.19-.59a1.29,1.29,0,0,0,1.06.85c-.63-.44-.6-1.61-.59-1.7,0-.59.55-.54.58-.89s-.53-.38-.53-.38.25,0,.3.12c.1.28-.37.31-.37.31-.58.15-.78-.19-1-.23s-.25.1-.3.15-.94.1-1.12.3a.48.48,0,0,0,0,.66.47.47,0,0,1,.42-.33,1.59,1.59,0,0,1,1,.68,6.54,6.54,0,0,1-1.59,0,.59.59,0,0,1-.22-.34s-.06.33.09.43a.37.37,0,0,0,.3.09c.08,0,1.32,0,1.45,0,0,.09,0,.33-.27.36h-1s0,.25.37.14c.08,0,.35-.09.43.05S62.64,27.19,62.05,27.28Z"/>\n      <path class="cls-6" d="M62.71,36.17a1.36,1.36,0,0,1-1,0s0,.17-.54.4a1.42,1.42,0,0,0-.56,2.5s-.47-1.45.26-1.79c0,0,.63.62,1.55-.61A2.13,2.13,0,0,0,62.71,36.17Z"/>\n      <path class="cls-6" d="M60.65,31.05c0,.38-.08.4-.43.57a1.35,1.35,0,0,1-.2-.26c-.21-.41.14-1,.14-1a.94.94,0,0,1-.95.32c0-.41.59-.78.59-.78a1.3,1.3,0,0,1-.9-.19,2.57,2.57,0,0,1,.67-.6,1.57,1.57,0,0,1-.87-.35,2.7,2.7,0,0,1,.73-.51,2.06,2.06,0,0,1-.55-.64,1.64,1.64,0,0,1,.85-.16c-.73-.54.05-2,.05-2-.11,2.18,1.58,1.61,1.45,2.73-.11.91-1.11.24-1.11.24-.17,1.28.56,1.4.56,1.4s0,.31,0,.63S60.67,30.87,60.65,31.05Z"/>\n      <path class="cls-6" d="M58.43,34.23a2.66,2.66,0,0,0,2.74-1.81,1.8,1.8,0,0,1-.26-.5l0-.09a3,3,0,0,1-.74.38,4.82,4.82,0,0,1-.42-.41,1.42,1.42,0,0,1-.26-.56,1.23,1.23,0,0,1-.75-.34,1.38,1.38,0,0,1,.12-.66,2.45,2.45,0,0,1-.57-.42,2.4,2.4,0,0,1,.31-.52c-.44-.35-.46-.56-.46-.56a1.73,1.73,0,0,1,.52-.6,3.06,3.06,0,0,1-.34-.69,1.76,1.76,0,0,1,.63-.42,1.45,1.45,0,0,1,0-.55s-2.67-1.39-3-2.29a6.83,6.83,0,0,0-.07,1.31c0,.46.75,1.21,2.46,2.36a4.77,4.77,0,0,1-2.8-1.29,4.59,4.59,0,0,0,.17,1.3c.15.39.9.67,2.57,1.5a2.86,2.86,0,0,1-2.71-.48,6.28,6.28,0,0,0,.5,1.15c.18.28.87.74,2.49.5a2.43,2.43,0,0,1-2.53,1s.08.71.55.92,1.09.25,2.27-.67A2,2,0,0,1,56.39,33a3,3,0,0,0,.86.94c.41.22,1.24,0,2.6-1.43A2,2,0,0,1,58.43,34.23Z"/>\n      <path class="cls-6" d="M61.42,32.9A5.42,5.42,0,0,1,62,34s-.9.78-.74,1.63a1.55,1.55,0,0,1-.1-1.09s.12-.3.12-.3a1.72,1.72,0,0,1-1.3.09s.56.07,1.17-.91C61.5,32.87,61.42,32.9,61.42,32.9Z"/>\n      <path class="cls-6" d="M58.42,35.53c-.1,0-.51-.15-.62.16s.3.52.54.31.66-.22.75-.06.1.23-.26.5c-.1.08-.69.45-.28.83.14.14.52.08.62-.45s.19-.6.34-.66a.45.45,0,0,1,.44,0l.11.09a.26.26,0,0,0,.42-.26c-.06-.26-.27-.2-.42-.12a.42.42,0,0,1-.25,0c-.1-.05-.14-.17,0-.25a1.59,1.59,0,0,0,.85-.72,1.48,1.48,0,0,1-.63-.07s-.63.85-1.12.63a.58.58,0,0,1-.22-.45.26.26,0,0,0-.44-.21c-.14.18,0,.36.18.41s.22.16.17.25S58.49,35.52,58.42,35.53Z"/>\n      <path class="cls-6" d="M58.17,34.59a.28.28,0,0,0-.14.18.29.29,0,0,0-.43.11S57.65,34.41,58.17,34.59Z"/>\n      <path class="cls-6" d="M57.56,35.78a.35.35,0,0,0,.06.32s-.32.12-.11.52A.53.53,0,0,1,57.56,35.78Z"/>\n      <path class="cls-6" d="M58.21,37.19a.35.35,0,0,0,.16.28s-.25.23.09.53A.53.53,0,0,1,58.21,37.19Z"/>\n      <path class="cls-6" d="M60.7,36.24c.08,0,.16.12.12.35a.34.34,0,0,0-.11-.57l-.05,0a.27.27,0,0,1,0,.23Z"/>\n      <path class="cls-6" d="M65.73,36.22c-.08,0-.16.12-.12.35a.34.34,0,0,1,.11-.57l0,0a.27.27,0,0,0,0,.23Z"/>\n      <path class="cls-6" d="M63.24,27.82a.62.62,0,0,0,.32-.23,1.34,1.34,0,0,0,.82.32c.53,1.39,1.68,2.24.62,4.12s-1.91,2.24-.36,3.59c0,0-1,.27-1.22-.58,0,0,0,.94-.18,1.19-.23-.25-.19-1.18-.19-1.18-.23.86-1.22.58-1.22.58,1.55-1.35.75-1.61-.36-3.58s.09-2.74.62-4.13a1.53,1.53,0,0,0,.84-.32A.49.49,0,0,0,63.24,27.82Z"/>\n      <path class="cls-6" d="M63.77,36.17a1.33,1.33,0,0,0,1,0s0,.17.54.4a1.42,1.42,0,0,1,.56,2.5s.47-1.45-.26-1.79c0,0-.63.62-1.54-.61A1.8,1.8,0,0,1,63.77,36.17Z"/>\n      <path class="cls-6" d="M65.82,31.05c0,.38.08.4.43.57a1.35,1.35,0,0,0,.2-.26c.21-.41-.14-1-.14-1a.94.94,0,0,0,1,.32c0-.41-.59-.78-.59-.78a1.3,1.3,0,0,0,.9-.19,2.57,2.57,0,0,0-.67-.6,1.57,1.57,0,0,0,.87-.35,2.7,2.7,0,0,0-.73-.51,2.06,2.06,0,0,0,.55-.64,1.64,1.64,0,0,0-.85-.16c.73-.54,0-2,0-2,.11,2.18-1.58,1.61-1.45,2.73.11.91,1.11.24,1.11.24.17,1.28-.56,1.4-.56,1.4s0,.31,0,.63S65.81,30.87,65.82,31.05Z"/>\n      <path class="cls-6" d="M68,34.23a2.66,2.66,0,0,1-2.74-1.81,1.8,1.8,0,0,0,.26-.5l0-.09a3.22,3.22,0,0,0,.74.38,3.71,3.71,0,0,0,.42-.41,1.42,1.42,0,0,0,.26-.56,1.24,1.24,0,0,0,.76-.34,1.46,1.46,0,0,0-.13-.66,2.45,2.45,0,0,0,.57-.42,2.4,2.4,0,0,0-.31-.52c.44-.35.46-.56.46-.56a1.73,1.73,0,0,0-.52-.6,3.06,3.06,0,0,0,.34-.69,1.76,1.76,0,0,0-.63-.42,1.45,1.45,0,0,0,0-.55s2.67-1.39,3-2.29a6.51,6.51,0,0,1,.08,1.31c-.05.46-.76,1.21-2.47,2.36A4.77,4.77,0,0,0,71,26.57a4.59,4.59,0,0,1-.17,1.3c-.15.39-.89.67-2.57,1.5a2.86,2.86,0,0,0,2.71-.48,6.28,6.28,0,0,1-.5,1.15c-.18.28-.87.74-2.49.5a2.43,2.43,0,0,0,2.53,1s-.08.71-.55.92-1.09.25-2.27-.67A2,2,0,0,0,70.08,33a3,3,0,0,1-.86.94c-.41.22-1.24,0-2.6-1.43A2.07,2.07,0,0,0,68,34.23Z"/>\n      <path class="cls-6" d="M65.05,32.9a5.42,5.42,0,0,0-.6,1.06s.9.78.74,1.63a1.55,1.55,0,0,0,.1-1.09s-.12-.3-.12-.3a1.72,1.72,0,0,0,1.3.09s-.56.07-1.17-.91C65,32.87,65.05,32.9,65.05,32.9Z"/>\n      <path class="cls-6" d="M68.05,35.53c.11,0,.51-.15.62.16s-.3.52-.54.31-.65-.22-.75-.06-.09.23.26.5c.1.08.69.45.28.83-.14.14-.52.08-.62-.45s-.19-.6-.34-.66-.31-.11-.43,0l-.12.09A.26.26,0,0,1,66,36c.06-.26.27-.2.42-.12a.42.42,0,0,0,.25,0c.1-.05.14-.17,0-.25a1.59,1.59,0,0,1-.85-.72,1.48,1.48,0,0,0,.63-.07s.63.85,1.12.63a.55.55,0,0,0,.22-.45.26.26,0,0,1,.44-.21c.15.18,0,.36-.18.41s-.22.16-.17.25S68,35.52,68.05,35.53Z"/>\n      <path class="cls-6" d="M68.3,34.59a.25.25,0,0,1,.14.18.29.29,0,0,1,.43.11S68.82,34.41,68.3,34.59Z"/>\n      <path class="cls-6" d="M68.91,35.78a.35.35,0,0,1-.06.32s.32.12.11.52A.53.53,0,0,0,68.91,35.78Z"/>\n      <path class="cls-6" d="M68.26,37.19a.35.35,0,0,1-.16.28s.25.23-.09.53A.53.53,0,0,0,68.26,37.19Z"/>\n      <path class="cls-6" d="M63.23,36.9a.65.65,0,0,0,.23-.14A2,2,0,0,0,65.4,38s-.08.3-.61.34c0,0,.91.42.39.84-.35.28-.62-.5-.62-.5s0,.72-.65.72c0,0,.91-.54,0-1.79.1.88-.21,1.7-.62,1.7h0c-.42,0-.73-.82-.63-1.7-1,1.25,0,1.79,0,1.79-.62,0-.66-.72-.66-.72s-.27.78-.61.5c-.53-.42.38-.84.38-.84-.53,0-.61-.34-.61-.34A2,2,0,0,0,63,36.76.72.72,0,0,0,63.23,36.9Z"/>\n      <path class="cls-7" d="M63.11,25.21v0l0-.16v0h0l-.72.28h0l.39,0a.26.26,0,0,0,0,.08.16.16,0,0,0,.16.16.17.17,0,0,0,.17-.16.19.19,0,0,0,0-.09l.12,0Z"/>\n      <path class="cls-7" d="M65.09,30.25a.65.65,0,0,0-.4-.37.39.39,0,0,0-.06-.11.54.54,0,0,0-.63-.2l-.15.07,0-.06h0a.84.84,0,0,0,.11-.2.53.53,0,0,0-.2-.63.24.24,0,0,0-.11-.06.65.65,0,0,0-.37-.4l-.07,0-.07,0a.65.65,0,0,0-.37.4l-.12.06a.53.53,0,0,0-.19.63.9.9,0,0,0,.1.2h0l.05.06-.16-.07a.54.54,0,0,0-.63.2.39.39,0,0,0-.06.11.65.65,0,0,0-.4.37l0,.07,0,.07a.65.65,0,0,0,.4.37.24.24,0,0,0,.06.11.54.54,0,0,0,.63.2.71.71,0,0,0,.2-.1h0l.07-.06v.65l-.07-.06-.1.13h0a.71.71,0,0,0-.1.2.53.53,0,0,0,.19.63l.12.06a.62.62,0,0,0,.37.4l.07,0,.07,0a.65.65,0,0,0,.37-.4.24.24,0,0,0,.11-.06.54.54,0,0,0,.2-.63.67.67,0,0,0-.11-.2h0l-.1-.13-.08.06v-.64l.07.05h0a.71.71,0,0,0,.2.1.54.54,0,0,0,.63-.2.39.39,0,0,0,.06-.11.65.65,0,0,0,.4-.37l0-.07Z"/>\n      <path class="cls-6" d="M64.71,30.3a.35.35,0,0,0-.34-.14.23.23,0,0,0,0-.21.21.21,0,0,0-.25-.09l0,0,0,0a.24.24,0,0,1,0,.08.17.17,0,0,1-.08.16.38.38,0,0,1-.18,0h-.45v-.68a.38.38,0,0,1,0-.18.17.17,0,0,1,.16-.08l.07,0,0,0,0,0a.21.21,0,0,0-.09-.25.23.23,0,0,0-.21,0,.35.35,0,0,0-.14-.34h0a.34.34,0,0,0-.15.34.23.23,0,0,0-.21,0,.19.19,0,0,0-.08.25v0l0,0,.07,0a.17.17,0,0,1,.16.08.26.26,0,0,1,0,.17h0v.68h-.47a.38.38,0,0,1-.18,0,.17.17,0,0,1-.08-.16.24.24,0,0,1,0-.08l0,0,0,0a.21.21,0,0,0-.25.09.2.2,0,0,0,0,.21.35.35,0,0,0-.34.14h0a.34.34,0,0,0,.34.15.22.22,0,0,0,.27.29h0l0,0a.25.25,0,0,1,0-.07.17.17,0,0,1,.08-.16.35.35,0,0,1,.17,0h.48V31.7h0a.26.26,0,0,1,0,.17.17.17,0,0,1-.16.08l-.07,0,0,0v0a.19.19,0,0,0,.08.25.2.2,0,0,0,.21,0,.34.34,0,0,0,.15.34h0a.35.35,0,0,0,.14-.34.2.2,0,0,0,.21,0,.21.21,0,0,0,.09-.25l0,0,0,0-.07,0a.17.17,0,0,1-.16-.08.38.38,0,0,1,0-.18V30.46h.46a.35.35,0,0,1,.17,0,.17.17,0,0,1,.08.16.25.25,0,0,1,0,.07l0,0h0a.2.2,0,0,0,.25-.08.23.23,0,0,0,0-.21.34.34,0,0,0,.34-.15h0Z"/>\n    </g>\n    <line class="cls-8" x1="84.04" x2="84.04" y2="42.53"/>\n  </g>\n</svg>\n') : (this.SVGLogo = '<svg id="mcmaster-logo-header"  style="' + t + '" xmlns="https://www.w3.org/2000/svg" viewBox="0 0 236.2 131" title="McMaster Univeristy Logo" alt="McMaster Univeristy Logo"><g id="letterstop">' + ('<path  class="letters" style="' + e.logoLetters + '"  d="M45.2 40.9H45c-.8 0-1.4-.1-1.9-.7-.6-.8-.6-3.3-.5-4.3v-28V7c0-1.1-.1-3.1.4-3.8.2-.2 1-.1 1.7-.1h.4c1.9 0 2-1.3 2-1.7 0-.5-.1-.8-.4-1.1-.4-.4-1-.3-1.5-.3h-7c-.7 0-1.7 0-2.2 1.3L24.2 31.7 14.5 4.4c-.4-1.2-.6-1.7-.7-1.9 0-.1-.1-.3-.1-.4V2c-.3-.9-.6-2-2-2h-7-.3C4 0 3.3-.1 2.9.3c-.3.3-.4.6-.4 1.1 0 .4.1 1.7 2 1.7 1.3 0 2.1.1 2.4.4.3.4.3 1.3.2 2.9 0 .3-1.9 29.7-1.9 29.8-.2 3.5-.4 4.7-3.1 4.7-1.9 0-2.1 1-2.1 1.5s.2 1.4 1.5 1.4c.9 0 1.8-.1 2.7-.1.9-.1 1.8-.1 2.7-.1.9 0 1.8.1 2.7.1.9.1 1.8.1 2.7.1.5 0 1.9 0 1.9-1.4 0-.4-.1-.7-.4-.9-.5-.5-1.4-.5-1.9-.5h-.1c-1.2 0-2-.3-2.5-.8-1.1-1.1-1-3.4-.9-6.3l1.6-26 10.9 31.6c.2.6.3.8.4 1v.1c.1.5.4 1.7 1.4 1.7.9 0 1.2-.9 1.4-1.4 0-.1 0-.1.1-.2L36.7 7.2v28.9c0 1.2 0 3.3-.7 4-.5.5-1.7.8-2.4.8h-.2c-.5 0-1.3 0-1.9.5-.3.3-.4.6-.4 1 0 .5.2 1.4 1.7 1.4 1.2 0 2.4-.1 3.5-.1 1.2-.1 2.4-.1 3.6-.1 1 0 1.9.1 2.9.1.9.1 1.9.1 2.9.1 1.5 0 1.7-.9 1.7-1.4 0-.4-.1-.7-.4-1-.4-.5-1.3-.5-1.8-.5z"></path>') + ('<path  class="letters" style="' + e.logoLetters + '" d="M60.2 44.6c3.6 0 6.9-1.2 9.6-3.6 1.8-1.7 2.1-2.5 2.1-2.9 0-.6-.5-1.1-1-1.1s-.9.4-1.3.9c0 .1-.1.1-.1.1-1.8 1.9-4.1 2.9-6.9 2.9-7 0-11.3-7.2-11.3-13.9 0-4.2 1.6-8.3 4.4-10.9 1.4-1.4 3.9-2.7 6-2.7 2.8 0 4.3 2.7 5.6 4.9.9 1.6 1.6 2.8 2.7 2.8.3 0 .6-.1.8-.4.6-.7.6-2.1.5-3.5v-.3-.6c.1-1 .1-2.3-.8-2.9-2.2-1.7-5.7-2.4-8.1-2.4-9.2 0-17 8-17 17.5.2 8.6 6.9 16.1 14.8 16.1z"></path>') + ('<path  class="letters" style="' + e.logoLetters + '" d="M95.5 40.7c0-.1 0-.1.1-.1l12.6-33.4v28.9c0 1.2 0 3.3-.7 4-.5.5-1.7.8-2.4.8h-.2c-.5 0-1.3 0-1.9.5-.3.3-.4.6-.4 1 0 .5.2 1.4 1.7 1.4 1.2 0 2.4-.1 3.5-.1 1.2-.1 2.4-.1 3.6-.1 1 0 1.9.1 2.9.1.9.1 1.9.1 2.9.1 1.5 0 1.7-.9 1.7-1.4 0-.4-.1-.7-.4-1-.5-.5-1.3-.5-1.9-.5h-.2c-.8 0-1.4-.1-1.9-.7-.6-.8-.6-3.3-.5-4.3v-28V7c0-1.1-.1-3.1.4-3.8.3-.4 1.1-.4 1.7-.3h.4c1.9 0 2-1.3 2-1.7 0-.5-.1-.8-.4-1.1-.4-.4-1.1-.4-1.6-.3h-7c-.7 0-1.7 0-2.2 1.3L95.7 31.7l-10-28.2c-.2-.6-.3-.9-.4-1 0-.2-.1-.3-.1-.5-.3-.9-.6-2-2-2h-7.3c-.5 0-1.1-.1-1.6.3-.2.3-.3.6-.3 1.1 0 .4.1 1.7 2 1.7 1.3 0 2.1.1 2.4.4.3.4.3 1.3.2 2.9-1.8 29.6-1.9 29.8-1.9 29.8-.2 3.5-.4 4.7-3.1 4.7-1.9 0-2.1 1-2.1 1.5s.2 1.4 1.5 1.4c.9 0 1.8-.1 2.7-.1.9-.1 1.8-.1 2.7-.1.9 0 1.8.1 2.7.1.9.1 1.8.1 2.7.1.5 0 1.9 0 1.9-1.4 0-.4-.1-.7-.4-.9-.5-.5-1.4-.5-1.9-.5h-.1c-1.2 0-2-.3-2.5-.8-1.1-1.1-1-3.4-.9-6.3L81.5 8l10.8 31.4c.2.7.4 1 .4 1.2v.1c.1.5.4 1.7 1.4 1.7.9-.2 1.2-1.1 1.4-1.7z"></path>') + ('<path  class="letters" style="' + e.logoLetters + '" d="M135.3 40.3c.6 1.5 1.6 3.9 4 3.9 1.8 0 3.6-1.2 4.9-2.2l.1-.1c.6-.5 1.6-1.5 1.6-2.5 0-.6-.5-1.1-1-1.1s-.8.4-1.1.7c-.4.5-1 1-1.7 1-.3 0-.5-.1-.7-.3-.9-.9-.9-3.5-.9-4.6V17.7c0-1.7.1-3.4-1.4-4.8-1.3-1.3-3.4-2-6.2-2-4.1 0-8.7 1.9-11.8 5-1.3 1.2-2.8 3.4-2.8 5.4 0 .9.5 1.4 1.4 1.4.9 0 2.3-.6 2.9-1 1.1-.5 1.5-1.5 1.9-2.5l.1-.3c1.6-3.9 3.6-5.5 6.8-5.5 3.2 0 3.5 1.8 3.5 5.7v3.1c0 2.4 0 2.4-2.1 3.4 0 0-1.7.9-3 1.6-1 .5-1.9 1-1.9 1l-.4.2c-3.7 2-9.2 5-9.2 10.1 0 4 3.3 6.1 6.5 6.1 4.4 0 7.9-3.2 9.6-4.7.2-.2.4-.4.6-.5.1.2.2.6.3.9zm-6.5-9.7c.1-.1.4-.2.9-.5l4.9-2.7c.1 0 .2-.1.3-.1h.1c0 .2.1.5 0 1.1v4.4c0 2.2-.1 3.3-1.4 4.9-1.5 1.6-3.5 2.6-5.5 2.6-1.8 0-3.8-.9-3.8-3.6-.2-3.1 2-4.8 4.5-6.1zM159.4 23.7c-3.5-1.3-6.6-2.5-6.6-5.9 0-3 3.1-4.6 5.3-4.6 4.2 0 5.3 2.7 6 4.6.4 1.1.8 2 1.7 2 .3 0 .6-.1.8-.3.6-.7.5-2.1.4-3.4v-.3-.6c.1-1 .2-2.4-1.1-3-1.6-.7-5.1-1.2-6.8-1.2-3.2 0-5.8.8-7.8 2.4-2.3 1.9-3.6 4.3-3.6 7 0 5.8 5.5 7.8 9.5 9.2.3.1.5.2.6.2 2.8 1 5.7 2.4 5.7 6.2 0 4.1-3.7 6.3-7.2 6.3-5.2 0-6-3.8-6.5-6.6-.3-1.6-.6-3-1.8-3-1.2 0-1.3 1.4-1.4 2v.1s0 .6-.2 3.8v1.3c0 1 0 2.1 1.2 2.7 2.3 1.3 6.2 2.2 8.3 2.2 5.2 0 12.6-3.4 12.6-10.8.2-6.8-4.7-8.7-9.1-10.3zM185.4 38.3c-.4 0-.7.3-1.2.7-.8.7-2 1.7-3.4 1.7-.7 0-1.3-.2-1.8-.7-1.4-1.4-1.4-4.7-1.4-6.8v-18c0-.7.1-.9.2-.9.1-.1.5-.1.9-.1h4.9c.6 0 1.1.1 1.4-.3.4-.3.4-.9.4-1.4 0-.5 0-1.5-1.1-1.5H178c-.4 0-.5 0-.5-.8v-5c0-1.2-.7-1.4-1.1-1.4-.7 0-1 .7-1.2 1-1.4 3.2-3.1 4.9-5.9 6.9l-.1.1c-.3.3-.8.7-.8 1.3 0 .3.1.6.3.8.5.4 1.3.4 2 .4h1.1c0 .1.1.2.1.7v19.1c0 2.7-.1 5.9 1.5 8.1 1.1 1.5 3 2.4 5 2.4 2.3 0 4.5-1 6.3-2.8.4-.3 1.5-1.4 1.5-2.4.2-.5-.2-1.1-.8-1.1z"></path>') + ('<path  class="letters" style="' + e.logoLetters + '" d="M193.3 24.6h19.5c.3 0 1.3-.1 1.3-1.8 0-2.4-1-5.5-2.3-7.4-2.1-2.9-5.6-4.6-9.6-4.6-4.4 0-8.5 1.7-11.8 4.8-3.2 3.1-4.7 6.9-4.7 12.1 0 9.4 6.6 16.7 14.9 16.7 4.2 0 7.4-1.3 10.4-4.1 1.8-1.7 2.6-2.8 2.6-3.5 0-.6-.5-1.1-1.1-1.1-.5 0-.8.3-1.4 1-1.3 1.3-3.6 3.6-7.9 3.6-7.7 0-11.7-7.1-11.7-14.1 0-.8.1-1.3.2-1.4.4-.2.9-.2 1.6-.2zm.3-6.9c1.8-2.8 4.7-4.4 7.7-4.4 1.5 0 3.7.3 5.1 2 .9 1.1 1.5 2.6 1.5 3.8 0 1.2-.6 1.9-1.9 2.2-1.8.5-5.3.5-7.2.5H193.3c-.4 0-1 0-1.2-.1 0 0-.1-.1-.1-.2.1-1 1.1-3 1.6-3.8zM232 11.2c-3.4 0-5.7 3.1-7 4.8-.1.1-.2.2-.2.3v-.2-3.6c0-.3 0-.9-.3-1.2-.1-.1-.4-.3-.8-.3-.7 0-1.1.5-1.4.9l.1.1-.1-.1-.2.2c-1 1.3-3.6 3-5 3.5-.1 0-.2.1-.2.1-.6.2-1.6.5-1.6 1.6 0 .7.5 1.1 1.3 1.1h.8c.7 0 1.2.1 1.4.4.3.4.5 1.7.5 3.9v14.6c.1 2.6 0 3.8-2.4 4h-.3c-.6 0-2 .1-2 1.5 0 .8.6 1.3 1.5 1.3 1 0 2-.1 3-.1 1-.1 2-.1 3-.1.9 0 1.9 0 2.8.1 1 .1 2 .1 3.1.1.8 0 1.3-.5 1.3-1.3 0-1.3-1.4-1.4-2-1.5h-.3c-2.3-.2-2.4-1.4-2.4-4V24.6c0-2.6 0-4.3 1.3-6.4.7-.9 1.6-2.3 2.8-2.3.5 0 .8.4 1.4 1 .6.7 1.3 1.7 2.7 1.7 1.9 0 3.2-1.4 3.2-3.4.2-2.3-1.6-4-4-4zM24.6 51c-.5 0-1 0-1.5.1-.5 0-.9.1-1.4.1-.5 0-1.1 0-1.6-.1-.6 0-1.1-.1-1.7-.1-.4 0-.8.1-1 .4-.2.2-.3.5-.3.8 0 .4.2.6.3.7.4.4.9.4 1.2.4h.1c.8 0 1.4 0 1.7.6.3.6.3 2.8.3 3.6v11.6c0 1.9 0 3.6-1.2 4.9-1.6 1.8-4.1 2-5.5 2-1 0-4.3-.2-5.4-2.4-.7-1.3-.7-3.9-.7-5.6V55.6c0-1 0-1.7.2-2 .2-.2.7-.3 1.6-.3 1.3 0 1.5-.6 1.5-1.1 0-.7-.5-1.1-1.2-1.1s-1.4 0-2.1.1c-.7 0-1.4.1-2.1.1-.7 0-1.3 0-2-.1-.6 0-1.4-.1-2.1-.1-.4 0-.7.1-.9.3-.2.2-.3.5-.3.8 0 .5.3 1.1 1.5 1.1.9 0 1.4.1 1.6.3.3.3.3 1 .2 2v13.6c0 2.7 0 5.2 2.4 7 2.1 1.7 5.4 2 7.2 2 3.3 0 5.7-.8 7.3-2.3 2.2-2.1 2.2-4.3 2.2-6.9V58.1v-2-.7c0-1.7.1-2.2 1.3-2.2 1.4 0 1.7-.6 1.7-1.1 0-.2-.1-1.1-1.3-1.1zM45.1 75.7h-.2c-1.1-.1-1.2-.5-1.2-2.1v-7.5c0-1.9 0-3.9-1.2-5.6-1.1-1.6-2.7-2.4-4.8-2.4-2.6 0-4.4 1.7-5.5 2.7v-1.6c0-.3 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6 0 0-.1.1-.1.2-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1v8.5c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1.6 0 1-.4 1-1 0-1-1-1.1-1.4-1.1h-.1c-1.1-.1-1.2-.5-1.2-2.1V66c0-1.6.1-2.3 1-3.4.9-1 2-1.6 3.2-1.6 1.3 0 2.4.6 3 1.6.6 1 .6 2.5.6 3.8v7.2c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.7-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1.6 0 1-.4 1-1 .6-1-.5-1.1-.8-1.1zM55.6 75.7h-.2c-1.1-.1-1.2-.5-1.2-2.1V59.2c0-.2 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6l-.1.1c-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1v8.5c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1.6 0 1-.4 1-1 .3-.9-.7-1-1.1-1zM50.3 53.1c0 1.5.9 2.5 2.1 2.5 1.3 0 2.2-1 2.2-2.6 0-1.2-.8-2.5-2.1-2.5-1.2 0-2.2 1.1-2.2 2.6zM76.5 58.7c-.2-.2-.5-.2-.7-.2h-5.5c-.9 0-1.1.5-1.1.9 0 .7.5 1 1.6 1 .3 0 .9.1.9.5 0 .3-.2.9-.4 1.3 0 .1-.1.2-.1.3-.1.1-.2.5-.5 1.1l-3.3 8.1c-3.2-8.7-3.3-8.9-3.3-8.9l-.1-.1c-.1-.4-.5-1.3-.5-1.7 0-.6.7-.6.8-.6h.1c.3 0 .9 0 1.2-.3.2-.2.3-.4.3-.6 0-.3-.1-.6-.3-.7-.3-.3-.7-.3-.9-.3h-6.8c-.2 0-.5 0-.8.2 0 .3-.1.5-.1.8 0 .3.1.6.3.8.2.2.5.2.9.2 1.1.1 1.2.4 1.7 1.7l.1.3c2 5.4 5.3 14.3 5.3 14.4l.2.5c.1.5.5.8.9.8.6 0 .9-.7 1.1-1.1V77l-.1-.1h.1s5.2-12.6 5.3-12.7c.1-.2.2-.4.2-.6.5-1.4 1.1-2.9 2.3-3.1h.1c.3 0 1.3-.1 1.3-1.1.1-.1.1-.4-.2-.7zM81.3 66.5h11.3c.2 0 1-.1 1-1.3 0-1.5-.6-3.3-1.4-4.4-1.3-1.8-3.4-2.8-5.7-2.8-2.6 0-5.1 1-7 2.9-1.9 1.9-2.8 4.1-2.8 7.2 0 5.6 3.9 10 8.9 10 2.5 0 4.4-.8 6.2-2.5 1.4-1.3 1.6-1.9 1.6-2.2 0-.5-.4-.9-.9-.9-.4 0-.6.3-1 .6-.7.7-2 2-4.4 2-4.3 0-6.6-4-6.6-8 0-.5.1-.7.1-.7.1.1.5.1.7.1zm4.7-6.6c.8 0 2 .2 2.8 1.1.5.6.8 1.4.8 2 0 .6-.3.9-.9 1.1-1 .3-3 .3-4.1.3h-3-.7c0-.5.5-1.6.8-2 1-1.6 2.6-2.5 4.3-2.5zM105.7 58.3c-1.9 0-3.2 1.5-3.9 2.5v-1.6c0-.2 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6 0 0-.1.1-.1.2-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1v8.5c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1.6 0 1-.4 1-1 0-1-1-1.1-1.4-1.1h-.1c-1.1-.1-1.2-.5-1.2-2.1v-7.3c0-1.5 0-2.4.7-3.6.4-.5.9-1.2 1.4-1.2.2 0 .3.1.6.5s.8 1.1 1.8 1.1c1.2 0 2.1-.9 2.1-2.2.1-1.5-1-2.6-2.5-2.6zM117.2 65.5c-2-.7-3.7-1.4-3.7-3.2 0-1.6 1.7-2.5 2.8-2.5 2.3 0 2.9 1.4 3.3 2.5.3.6.5 1.3 1.2 1.3.2 0 .5-.1.6-.3.4-.5.4-1.3.3-2.2V61v-.4c0-.6.1-1.6-.8-2-1-.5-3-.7-4-.7-1.9 0-3.5.5-4.7 1.5-1.4 1.1-2.2 2.6-2.2 4.2 0 3.6 3.3 4.7 5.7 5.6l.3.1c2 .7 3.2 1.5 3.2 3.4 0 2.2-2 3.4-3.9 3.4-2.8 0-3.2-1.9-3.5-3.6-.2-1-.4-2-1.3-2s-1 1-1 1.3v.1l-.1 2.8v.2c0 .6 0 1.4.8 1.8 1.4.8 3.7 1.3 5 1.3 3.7 0 7.6-2.4 7.6-6.5 0-3.9-3-5-5.6-6zM131.8 53c0-1.2-.8-2.5-2.1-2.5-1.2 0-2.2 1.1-2.2 2.6s.9 2.5 2.1 2.5c1.4 0 2.2-1 2.2-2.6zM132.8 75.7h-.2c-1.1-.1-1.2-.5-1.2-2.1V59.2c0-.3 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6 0 0-.1.1-.1.2-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1v8.5c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1.6 0 1-.4 1-1 .3-1-.7-1.1-1.1-1.1zM144.4 74c-.3 0-.5.2-.9.5-.4.4-1.1 1-1.8 1-.4 0-.6-.1-.9-.3-.7-.7-.7-2.6-.7-3.8V60.8v-.4H143.4c.4 0 .7 0 1-.2.3-.3.3-.6.3-1 0-.8-.3-1.1-.9-1.1h-3.6-.1V55c0-1-.7-1.1-.9-1.1-.4 0-.7.2-.9.7-.8 1.8-1.8 2.8-3.3 3.9l-.1.1c-.2.2-.6.5-.6 1 0 .2.1.5.3.6.4.3.9.3 1.4.3h.4V71.9c0 1.6 0 3.5.9 4.8.7.9 1.8 1.5 3.1 1.5 1.4 0 2.7-.6 3.8-1.7.3-.3.9-.9.9-1.6.1-.4-.2-.9-.7-.9zM164.5 58.5h-5.8c-.6 0-1.1.5-1.1 1.1 0 .9 1 .9 1.4.9 1.4 0 1.4.7 1.4.9 0 .4-.3 1-.4 1.4v.1c0 .1-2.4 6.3-3.6 9.3l-3.6-9.6v-.1c-.2-.4-.4-1-.4-1.4 0-.7 1.2-.7 1.3-.7 1.2 0 1.5-.5 1.5-.9 0-.7-.5-1.1-1.1-1.1H147c-.7 0-1.3.4-1.3 1.1 0 .9 1.1.9 1.5.9.8 0 1.2.8 1.6 2.1 0 0 .1.3.2.4l4.8 12.7c0 .1.1.3.2.4.1.4.3.8.3 1.1 0 .3-.1.5-.2.8 0 .1-.1.2-.1.2-1 2.5-1.2 3.1-1.2 3.2 0 .1-.1.2-.1.2v.1c-.2.4-.3.8-.5.8-.3.1-.8.1-1.2.1h-.3c-1.7 0-1.7 1.6-1.7 2.2 0 .6.2 1 .5 1.3.5.5 1.3.6 2 .6h.2c1.7 0 1.9-.6 2.3-1.9v-.1l6.2-16.4c.8-2.1 1.1-2.8 1.1-3.1.3-.8 1.3-3.3 1.9-4.2.3-.4.9-.7 1.2-.7h.2c.4 0 1.1-.1 1.1-.8-.1-.4-.6-.9-1.2-.9z"></path>') + "</g>" + ('<path  id="shieldoutlinetop" class="shieldoutline" style="fill:' + e.shieldoutline + '" d="M234.8 49.6H174v46.1c1 11 12 29.3 30.2 34.9l.3.1.3.1.3.1.3-.1.3-.1.3-.1c18.2-5.6 29.2-24 30.2-35.2V49.8h-1.4zm-.5 1.9v44c-.9 10.7-11.6 28.3-29.2 33.8l-.3.1h-.2l-.3-.1c-17.6-5.4-28.3-23.1-29.2-33.7V51H234v.5z"></path>') + ('<path  id="shieldtop" class="shield" style="' + e.shield + '" d="M232.9 51.1h-57.6V95.7c.9 10.6 11.6 28.2 29.2 33.7l.3.1h.2l.3-.1c17.6-5.4 28.2-23.1 29.2-33.8V51.2h-1.6zm0 44.5c-.8 9.3-10.5 27-28.2 32.5-17.7-5.5-27.4-23.2-28.2-32.5v-27H232.8v27zm0-27h-56.4V52.5h56.4v16.1z"></path>') + '<g id="shieldbgtop">' + ('<path  class="shieldbg" style="' + e.shieldbg + '" d="M204.8 68.6H176.6v27c.8 9.3 10.5 27 28.2 32.5 17.7-5.5 27.4-23.2 28.2-32.5v-27h-28.2zm11.5 5.9s2.6 4.7.2 6.5c0 0 1.5-.2 2.8.5 0 0-.9 1.6-1.8 2.1 0 0 1.9.9 2.4 1.6 0 0-1.2 1-2.8 1.2 0 0 1.7 1.1 2.2 2 0 0-1.3.9-2.9.6 0 0 1.8 1.2 1.9 2.5 0 0-1.8.5-3.1-1 0 0 1.2 2 .5 3.3-.2.4-.7.8-.7.8-1.1-.6-1.3-.6-1.4-1.8 0-.6.1-.7.1-2 0-1.1-.2-2.1-.2-2.1s2.4-.4 1.8-4.6c0 0-3.2 2.2-3.6-.8-.5-3.6 5-1.7 4.6-8.8zm-2.9 35s-.1 0-.2.1c-.3.1-.5.4-.4 1.1 0 0-1-1.1.4-1.9l.1-.1c0 .1-.2.5.1.8zm-2-6.5s.3.8.4 1c.7 1.5-.3 3.6-.3 3.6.5-2.8-2.4-5.3-2.4-5.3.4-1.3 1.8-3.3 1.9-3.4 0 .1.1.4.8 1.5 2 3.2 3.8 3 3.8 3-1.7.8-4.2-.4-4.2-.4zm-.6-7.1c-3.6 6.4-6.2 7.3-1.2 11.7 0 0-3.2.9-4-1.9 0 0 .2 3.1-.6 3.9-.8-.8-.6-3.8-.6-3.8-.7 2.8-4 1.9-4 1.9 5-4.4 2.4-5.3-1.2-11.7-3.5-6.2.3-8.9 2-13.5.8-.1 2.1-.4 2.7-1.1 0 0 .3.5 1 .7.7-.2 1.1-.7 1.1-.7.5.6 2 1 2.7 1 1.8 4.6 5.6 7.4 2.1 13.5zm-12.1 11.7s-1-2-.3-3.6c.1-.1.4-1 .4-1s-2.5 1.2-4.2.3c0 0 1.8.2 3.8-3 .7-1.2.8-1.5.8-1.5.1.2 1.5 2.1 1.9 3.4 0 0-3 2.6-2.4 5.4zm-1.9 2.1c-.1 0-.2-.1-.2-.1.2-.3.1-.7.1-.7.1 0 .1.1.1.1 1.4.8.4 1.9.4 1.9.1-.9-.2-1.1-.4-1.2zm1.2-34.3c0 .3.4.9.7 1.1.5.4 4.7.1 5.2.1-.4-.8-2.3-2.3-3.3-2.2-1.1 0-1.4 1.1-1.4 1.1-.5-.5-.6-1.4.1-2.1.6-.6 3.5-.8 3.7-1 .1-.2.3-.6 1-.5.7.1 1.3 1.2 3.2.8 0 0 1.5-.1 1.2-1-.1-.4-1-.4-1-.4s1.9-.3 1.7 1.2c-.1 1.1-1.8 1-1.9 2.9 0 .3-.1 4.1 1.9 5.6 0 0-2.5-.2-3.5-2.8 0 0 0 1.9-.6 1.9s-.8-1.9-.8-1.9c-.2 2.5-3.1 2.3-3.1 2.3 2-.3 1.4-1.3 1.2-1.6-.3-.5-1.1-.2-1.4-.2-1.3.4-1.2-.5-1.2-.5h3.3c.9-.1.8-.9.9-1.2-.4 0-4.5.1-4.8.1-.3 0-.5 0-1-.3-.4-.3-.1-1.4-.1-1.4zm-4.2-.9c-.4 7.1 5.1 5.3 4.7 8.9-.4 3-3.6.8-3.6.8-.6 4.2 1.8 4.6 1.8 4.6s-.1 1-.2 2.1c0 1.3.1 1.4.1 2-.1 1.2-.3 1.3-1.4 1.8 0 0-.4-.4-.7-.8-.7-1.3.5-3.3.5-3.3-1.3 1.6-3.1 1-3.1 1 .1-1.3 1.9-2.5 1.9-2.5-1.6.3-2.9-.6-2.9-.6.5-.9 2.2-2 2.2-2-1.7-.1-2.8-1.2-2.8-1.2.5-.7 2.4-1.6 2.4-1.6-.9-.5-1.8-2.1-1.8-2.1 1.3-.7 2.8-.5 2.8-.5-2.5-1.9.1-6.6.1-6.6zM182.7 99s5.7 1.8 8-4c-3.8 3-6.3 2.7-7.4 2.2-1.5-.7-1.8-3-1.8-3 2.5 1.2 6.3-.7 8.3-3.1-5.3.8-7.5-.7-8.1-1.6-.9-1.4-1.7-3.8-1.7-3.8 1.4 1.4 6.2 3 8.9 1.5-5.5-2.7-7.9-3.6-8.4-4.9-.6-1.6-.6-4.2-.6-4.2 1 1.8 5.7 3.7 9.2 4.2-5.6-3.7-7.9-6.2-8-7.7-.2-1.7.2-4.3.2-4.3 1 2.9 9.6 7.5 9.6 7.5 0 .6-.1 1.2.1 1.8 0 0-1 .3-2.1 1.4 0 0 .5 1.5 1.1 2.3 0 0-1.3 1-1.7 1.9 0 0 .1.7 1.5 1.8 0 0-.4.4-1 1.7 0 0 .9.9 1.9 1.4 0 0-.5 1-.4 2.2 0 0 1.2 1.1 2.5 1.1 0 0 .1.8.9 1.8.3.4 1.4 1.3 1.4 1.3s1.9-.7 2.4-1.3l.1.3s.1.6.8 1.6c0 0-1.4 5.7-8.9 5.9 4.3-1.4 4.6-5.7 4.6-5.7-4.4 4.8-7.1 5.4-8.5 4.7-1.6-.7-2.9-3-2.9-3zm3.7 11.9s-1.5-1.4.2-2.8c0 0-.2.4.2 1-.1.1-1.1.5-.4 1.8zm.3-5.7s.2-1.5 1.9-.9c0 0-.4.2-.5.6 0 0-.9-.6-1.4.3zm2 7.6s0 .5.5.9c0 0-.8.7.3 1.7 0 0-2-.8-.8-2.6zm5.6-3.4c-.4-.3-1.2-.1-1.4 0-.5.2-.9.9-1.1 2.2-.3 1.7-1.6 1.9-2 1.5-1.3-1.3.6-2.5.9-2.7 1.1-.9 1-1.4.8-1.6-.3-.5-1.6-.5-2.5.2-.8.7-2.1.2-1.7-1 .3-1 1.7-.5 2-.5.2 0 .5.1.7-.2.2-.3-.3-.7-.6-.8-.5-.2-1-.8-.6-1.3.5-.6 1.4-.2 1.4.7 0 .4.2 1.2.7 1.5 1.6.7 3.7-2 3.7-2s.9.3 2 .2c0 0-.5 1.3-2.8 2.4-.5.3-.4.6-.1.8 0 0 .5.1.8 0 .5-.2 1.2-.4 1.4.4.2.8-.7 1.3-1.4.8.2-.3-.1-.5-.2-.6zm2.3 9.6c-3.7-4.2-.9-7 1.8-8.1 1.8-.8 1.7-1.3 1.7-1.3s2 .6 3.2-.1c0 0-.3.9-.9 1.8-3 4-5 2-5 2-2.4 1-.8 5.7-.8 5.7zm14.8.3c-1.1.9-2-1.6-2-1.6s-.1 2.3-2.1 2.4c0 0 3-1.8-.1-5.9.3 2.9-.7 5.6-2.1 5.6-1.4 0-2.4-2.7-2.1-5.6-3.1 4.1-.1 5.9-.1 5.9-2 0-2.1-2.4-2.1-2.4s-.9 2.5-2 1.6c-1.7-1.4 1.3-2.8 1.3-2.8-1.7-.1-2-1.1-2-1.1 4.4.5 6.3-4.1 6.3-4.1.3.3.5.3.7.4.2-.1.5-.2.7-.4 0 0 1.9 4.6 6.3 4.1 0 0-.3 1-2 1.1 0 .1 3 1.4 1.3 2.8zm2.1-.3s1.5-4.7-.8-5.8c0 0-2.1 2-5-2-.6-.8-.9-1.8-.9-1.8 1.2.8 3.2.1 3.2.1s-.1.6 1.7 1.3c2.7 1.2 5.5 4.1 1.8 8.2zm7.1-3.6c1.1-1 .3-1.7.3-1.7.6-.5.5-.9.5-.9 1.1 1.8-.8 2.6-.8 2.6zm.4-6.5c-.8-.7-2.1-.7-2.5-.2-.1.2-.3.8.8 1.6.4.3 2.3 1.5.9 2.7-.5.4-1.7.3-2-1.5-.2-1.3-.6-1.9-1.1-2.2-.2-.1-1-.3-1.4 0-.1.1-.4.3-.4.3-.7.5-1.6-.1-1.4-.8.2-.9.9-.7 1.4-.4.4.2.8 0 .8 0 .3-.2.4-.5-.1-.8-2.3-1.1-2.8-2.4-2.8-2.4 1.1.1 2-.2 2-.2s2.1 2.8 3.7 2c.5-.2.7-1.1.7-1.5 0-.8.9-1.3 1.4-.7.5.6-.1 1.1-.6 1.3-.3.1-.7.5-.6.8.2.3.4.2.7.2.3 0 1.7-.5 2 .5.7 1.4-.7 2-1.5 1.3zm1-4c-.1-.4-.5-.6-.5-.6 1.7-.6 1.9.9 1.9.9-.6-.9-1.4-.3-1.4-.3zm1.7 6c.7-1.3-.3-1.7-.3-1.7.4-.6.2-1 .2-1 1.6 1.3.1 2.7.1 2.7zm6.4-25.2s-.8 2.3-1.7 3.8c-.6.9-2.8 2.4-8.1 1.6 2 2.4 5.7 4.3 8.3 3.1 0 0-.3 2.3-1.8 3-1.1.5-3.6.8-7.4-2.2 2.3 5.7 8 4 8 4s-1.3 2.3-2.8 3.1c-1.3.7-4 .1-8.5-4.7 0 0 .3 4.3 4.6 5.7-7.6-.2-8.9-5.9-8.9-5.9.7-1.1.8-1.6.8-1.6l.1-.3c.5.5 2.4 1.3 2.4 1.3s1.1-1 1.4-1.3c.7-1.1.9-1.8.9-1.8 1.3 0 2.5-1.1 2.5-1.1.1-1.2-.4-2.2-.4-2.2.9-.4 1.9-1.4 1.9-1.4-.6-1.3-1-1.7-1-1.7 1.5-1.1 1.5-1.8 1.5-1.8-.4-1-1.7-1.9-1.7-1.9.6-.8 1.1-2.3 1.1-2.3-1.1-1.1-2.1-1.4-2.1-1.4.2-.6.1-1.2.1-1.8 0 0 8.7-4.5 9.6-7.5 0 0 .4 2.6.2 4.3-.1 1.5-2.5 3.9-8 7.7 3.4-.5 8.1-2.4 9.2-4.2 0 0 0 2.7-.6 4.2-.5 1.3-2.9 2.2-8.4 4.9 2.7 1.4 7.4-.2 8.8-1.6z"></path>') + ('<path  class="shieldbg" style="' + e.shieldbg + '" d="M211.1 90.1c-.4-.8-.9-1.1-1.3-1.2-.1-.1-.1-.2-.2-.4-.5-.8-1.4-.9-2.1-.6-.2.1-.4.2-.5.2l.1-.2c.1-.1.2-.3.3-.6.2-.6.1-1.5-.6-2.1-.1-.1-.2-.1-.4-.2-.1-.4-.4-.9-1.2-1.3l-.2-.1-.2.1c-.8.4-1.1.9-1.2 1.3-.1 0-.2.1-.4.2-.8.5-.9 1.4-.6 2.1.1.4.2.5.3.6l.2.2c-.1-.1-.3-.1-.5-.2-.6-.2-1.5-.1-2.1.6-.1.1-.1.2-.2.4-.4.1-.9.4-1.3 1.2l-.1.2.1.2c.4.8.9 1.1 1.3 1.2 0 .1.1.2.2.4.5.8 1.4.9 2.1.6.4-.1.5-.2.6-.3l.2-.2v2.1l-.2-.2-.3.4c-.1.1-.2.3-.3.6-.2.6-.1 1.5.6 2.1.1.1.2.1.4.2.1.4.4.9 1.2 1.3l.2.1.2-.1c.8-.4 1.1-.9 1.2-1.3.1 0 .2-.1.4-.2.8-.5.9-1.4.6-2.1-.1-.4-.2-.5-.3-.6l-.3-.4-.2.2v-2.1l.2.2c.1.1.3.2.6.3.6.2 1.5.1 2.1-.6.1-.1.1-.2.2-.4.4-.1.9-.4 1.3-1.2l.1-.2v-.2zm-1.2.3s-.1 0 0 0c0 .1-.5.7-1.1.5.1.2.1.4-.1.7-.3.4-.7.3-.8.3h-.1l.1-.1s.1-.1.1-.2 0-.3-.3-.5c-.1-.1-.4-.1-.6-.1h-1.5v4c0 .1 0 .5.1.6.2.2.4.3.5.3.1 0 .2-.1.2-.1l.1-.1v.1c.1.2.1.6-.3.8-.3.2-.5.1-.7.1.2.6-.5 1.1-.5 1.1s-.6-.5-.5-1.1c-.2.1-.4.1-.7-.1-.4-.3-.3-.7-.3-.8v-.1l.1.1s.1.1.2.1.3 0 .5-.3c.1-.1.1-.4.1-.6v-4h-1.6c-.1 0-.4 0-.6.1-.2.2-.3.4-.2.5 0 .1.1.2.1.2l.1.1h-.1c-.2.1-.6.1-.8-.3-.2-.3-.1-.5-.1-.7-.6.2-1.1-.5-1.1-.5s.5-.6 1.1-.5c-.1-.2-.1-.4.1-.7.3-.4.7-.3.8-.3h.1l-.1.1s-.1.1-.1.2 0 .3.2.5c.1.1.5.1.6.1h1.6v-2.2c0-.1 0-.4-.1-.6-.2-.2-.4-.3-.5-.3-.1 0-.2.1-.2.1l-.1.1v-.1c-.1-.2-.1-.6.3-.8.3-.2.5-.1.7-.1-.2-.6.5-1.1.5-1.1s.6.5.5 1.1c.2-.1.4-.1.7.1.4.3.3.7.3.8v.1l-.1-.1s-.1-.1-.2-.1-.3 0-.5.3c-.1.1-.1.5-.1.6v2.2h1.5c.1 0 .5 0 .6-.1.2-.2.3-.4.3-.5 0-.1-.1-.2-.1-.2l-.1-.1h.1c.2-.1.6-.1.8.3.2.3.1.5.1.7.6-.2 1 .4 1.1.5zM204.2 74c0-.1 0-.2-.1-.3h.5v-.1l-.1-.5V73h-.1l-2.3.9 1.3-.1c0 .1-.1.2-.1.2 0 .3.2.5.5.5.2.1.4-.2.4-.5z"></path>') + '</g><g id="eagletop">' + ('<path  class="eagle" style="' + e.eagle + '" d="M202.4 111.2c.6-.8.9-1.8.9-1.8-1.2.8-3.2.1-3.2.1s.1.6-1.7 1.3c-2.7 1.1-5.5 4-1.8 8.1 0 0-1.5-4.7.8-5.8 0 .1 2.1 2.1 5-1.9zM193.6 80.9s-1.5-.2-2.8.5c0 0 .9 1.6 1.8 2.1 0 0-1.9.9-2.4 1.6 0 0 1.2 1 2.8 1.2 0 0-1.7 1.1-2.2 2 0 0 1.3.9 2.9.6 0 0-1.8 1.2-1.9 2.5 0 0 1.8.5 3.1-1 0 0-1.2 2-.5 3.3.2.4.7.8.7.8 1.1-.6 1.3-.6 1.4-1.8 0-.6-.1-.7-.1-2 0-1.1.2-2.1.2-2.1s-2.4-.4-1.8-4.6c0 0 3.2 2.2 3.6-.8.4-3.6-5.1-1.8-4.7-8.9.1.2-2.5 4.9-.1 6.6z"></path>') + ('<path  class="eagle" style="' + e.eagle + '" d="M194 97.4s-.3 4.3-4.6 5.7c7.6-.2 8.9-5.9 8.9-5.9-.7-1.1-.8-1.6-.8-1.6l-.1-.3c-.5.5-2.4 1.3-2.4 1.3s-1.1-1-1.4-1.3c-.7-1.1-.9-1.8-.9-1.8-1.3 0-2.5-1.1-2.5-1.1-.1-1.2.4-2.2.4-2.2-.9-.4-1.9-1.4-1.9-1.4.6-1.3 1-1.7 1-1.7-1.5-1.1-1.5-1.8-1.5-1.8.4-1 1.7-1.9 1.7-1.9-.6-.8-1.1-2.3-1.1-2.3 1.1-1.1 2.1-1.4 2.1-1.4-.2-.6-.1-1.2-.1-1.8 0 0-8.7-4.5-9.6-7.5 0 0-.4 2.6-.2 4.3.1 1.5 2.5 3.9 8 7.7-3.4-.5-8.1-2.4-9.2-4.2 0 0 0 2.7.6 4.2.5 1.3 2.9 2.2 8.4 4.9-2.7 1.5-7.5-.2-8.9-1.5 0 0 .8 2.3 1.7 3.8.6.9 2.8 2.4 8.1 1.6-2 2.4-5.7 4.3-8.3 3.1 0 0 .3 2.3 1.8 3 1.1.5 3.6.8 7.4-2.2-2.3 5.7-8 4-8 4s1.3 2.3 2.8 3.1c1.5.6 4.2 0 8.6-4.8zM201.1 102.2c-.4-1.3-1.8-3.3-1.9-3.4 0 .1-.1.4-.8 1.5-2 3.2-3.8 3-3.8 3 1.7.9 4.2-.3 4.2-.3s-.3.8-.4 1c-.7 1.5.3 3.6.3 3.6-.6-2.8 2.4-5.4 2.4-5.4zM199.1 98.8s.1 0 0 0c.1 0 0 0 0 0z"></path>') + ('<path  class="eagle" style="' + e.eagle + '" d="M196.1 108.9c-.2-.9-.9-.7-1.4-.4-.4.2-.8 0-.8 0-.3-.2-.4-.5.1-.8 2.3-1.1 2.8-2.4 2.8-2.4-1.1.1-2-.2-2-.2s-2.1 2.8-3.7 2c-.5-.2-.7-1.1-.7-1.5 0-.8-.9-1.3-1.4-.7-.5.6.1 1.1.6 1.3.3.1.7.5.6.8-.2.3-.4.2-.7.2-.3 0-1.7-.5-2 .5-.4 1.2 1 1.7 1.7 1 .8-.7 2.1-.7 2.5-.2.1.2.3.8-.8 1.6-.4.3-2.3 1.5-.9 2.7.5.4 1.7.3 2-1.5.2-1.3.6-1.9 1.1-2.2.2-.1 1-.3 1.4 0 .1.1.4.3.4.3.5.8 1.4.2 1.2-.5zM188.1 104.9c.1-.4.5-.6.5-.6-1.7-.6-1.9.9-1.9.9.5-.9 1.4-.3 1.4-.3zM186.5 108.2c-1.7 1.3-.2 2.8-.2 2.8-.7-1.3.3-1.7.3-1.7-.2-.7-.1-1.1-.1-1.1zM189.2 113.7c-.6-.5-.5-.9-.5-.9-1.1 1.8.8 2.6.8 2.6-1.1-1-.3-1.7-.3-1.7zM196.8 108.9l-.1-.1s.2.4-.1.7c0 0 .1 0 .2.1.3.1.5.4.4 1.1 0 .1 1-1-.4-1.8zM213.2 108.9c-1.4.8-.4 1.9-.4 1.9-.1-.7.1-1 .4-1.1.1 0 .2-.1.2-.1-.2-.3-.1-.7-.1-.7 0-.1-.1-.1-.1 0zM211.7 110.9c-1.8-.8-1.7-1.3-1.7-1.3s-2 .6-3.2-.1c0 0 .3.9.9 1.8 3 4 5 2 5 2 2.4 1.1.8 5.8.8 5.8 3.7-4.2.9-7.1-1.8-8.2zM215.2 84.2c.6 4.2-1.8 4.6-1.8 4.6s.1 1 .2 2.1c0 1.3-.1 1.4-.1 2 .1 1.2.3 1.3 1.4 1.8 0 0 .4-.4.7-.8.7-1.3-.5-3.3-.5-3.3 1.3 1.6 3.1 1 3.1 1-.1-1.3-1.9-2.5-1.9-2.5 1.6.3 2.9-.6 2.9-.6-.5-.9-2.2-2-2.2-2 1.7-.1 2.8-1.2 2.8-1.2-.5-.7-2.4-1.6-2.4-1.6.9-.5 1.8-2.1 1.8-2.1-1.3-.7-2.8-.5-2.8-.5 2.4-1.7-.2-6.5-.2-6.5.4 7.1-5.1 5.3-4.7 8.9.4 2.9 3.7.7 3.7.7z"></path>') + ('<path  class="eagle" style="' + e.eagle + '" d="M228.5 89.5c.9-1.4 1.7-3.8 1.7-3.8-1.4 1.4-6.2 3-8.9 1.5 5.5-2.7 7.9-3.6 8.4-4.9.6-1.6.6-4.2.6-4.2-1 1.8-5.7 3.7-9.2 4.2 5.6-3.7 7.9-6.2 8-7.7.2-1.7-.2-4.3-.2-4.3-1 2.9-9.6 7.5-9.6 7.5 0 .6.1 1.2-.1 1.8 0 0 1 .3 2.1 1.4 0 0-.5 1.5-1.1 2.3 0 0 1.3 1 1.7 1.9 0 0-.1.7-1.5 1.8 0 0 .4.4 1 1.7 0 0-.9.9-1.9 1.4 0 0 .5 1 .4 2.2 0 0-1.2 1.1-2.5 1.1 0 0-.1.8-.9 1.8-.3.4-1.4 1.3-1.4 1.3s-1.9-.7-2.4-1.3l-.1.3s-.1.6-.8 1.6c0 0 1.4 5.7 8.9 5.9-4.3-1.4-4.6-5.7-4.6-5.7 4.4 4.8 7.1 5.4 8.5 4.7 1.5-.8 2.8-3.1 2.8-3.1s-5.7 1.8-8-4c3.8 3 6.3 2.7 7.4 2.2 1.5-.7 1.8-3 1.8-3-2.5 1.2-6.3-.7-8.3-3.1 5.3.9 7.6-.6 8.2-1.5zM210.9 98.8s.1 0 0 0c.1 0 0 0 0 0zM215.6 103.3s-1.8.2-3.8-3c-.7-1.2-.8-1.5-.8-1.5-.1.2-1.5 2.1-1.9 3.4 0 0 2.9 2.5 2.4 5.3 0 0 1-2 .3-3.6-.1-.1-.4-1-.4-1s2.5 1.3 4.2.4z"></path>') + ('<path  class="eagle" style="' + e.eagle + '" d="M220.7 107.3c-.2 0-.5.1-.7-.2-.2-.3.3-.7.6-.8.5-.2 1-.8.6-1.3-.5-.6-1.4-.2-1.4.7 0 .4-.2 1.2-.7 1.5-1.6.7-3.7-2-3.7-2s-.9.3-2 .2c0 0 .5 1.3 2.8 2.4.5.3.4.6.1.8 0 0-.5.1-.8 0-.5-.2-1.2-.4-1.4.4-.2.8.7 1.3 1.4.8 0 0 .3-.2.4-.3.4-.3 1.2-.1 1.4 0 .5.2.9.9 1.1 2.2.3 1.7 1.6 1.9 2 1.5 1.3-1.3-.6-2.5-.9-2.7-1.1-.9-1-1.4-.8-1.6.3-.5 1.6-.5 2.5.2.8.7 2.1.2 1.7-1-.5-1.2-1.8-.7-2.2-.8zM221.5 104.3s.4.2.5.6c0 0 .8-.6 1.4.3 0 0-.1-1.5-1.9-.9zM223.5 108.2s.2.4-.2 1c0 0 1 .4.3 1.7.1 0 1.6-1.4-.1-2.7zM220.9 113.7s.8.7-.3 1.7c0 0 1.9-.8.8-2.6 0 0 .1.4-.5.9zM212.1 115.5c-4.4.5-6.3-4.1-6.3-4.1-.3.3-.5.3-.7.4-.2-.1-.5-.2-.7-.4 0 0-1.9 4.6-6.3 4.1 0 0 .3 1 2 1.1 0 0-3 1.4-1.3 2.8 1.1.9 2-1.6 2-1.6s.1 2.3 2.1 2.4c0 0-3-1.8.1-5.9-.3 2.9.7 5.6 2.1 5.6 1.4 0 2.4-2.7 2.1-5.6 3.1 4.1.1 5.9.1 5.9 2 0 2.1-2.4 2.1-2.4s.9 2.5 2 1.6c1.7-1.4-1.3-2.8-1.3-2.8 1.7-.2 2-1.1 2-1.1zM199.2 77.1c.3 0 4.3-.1 4.8-.1-.1.3 0 1.1-.9 1.2h-3.3s-.1.8 1.2.5c.3-.1 1.1-.3 1.4.2.2.3.8 1.4-1.2 1.6 0 0 2.9.2 3.1-2.3 0 0 .2 1.8.8 1.9.6 0 .6-1.9.6-1.9 1 2.6 3.5 2.8 3.5 2.8-2.1-1.4-2-5.3-1.9-5.6.1-1.9 1.8-1.7 1.9-2.9.2-1.6-1.7-1.2-1.7-1.2s.8 0 1 .4c.3.9-1.2 1-1.2 1-1.9.5-2.5-.6-3.2-.8-.7-.1-.8.3-1 .5-.1.2-3.1.3-3.7 1-.7.7-.6 1.6-.1 2.1 0 0 .3-1 1.4-1.1 1.1 0 2.9 1.4 3.3 2.2-.5 0-4.6.3-5.2-.1-.3-.3-.7-.8-.7-1.1 0 0-.2 1.1.3 1.4.4.4.5.3.8.3zm4.5-2.5c-.3 0-.5-.2-.5-.5 0-.1 0-.2.1-.2l-1.3.1 2.3-.9h.1v.1l.1.5v.1h-.5c.1.1.1.2.1.3.1.2-.1.5-.4.5zM208.8 82.5c-.7-.1-2.2-.4-2.7-1 0 0-.3.5-1.1.7-.7-.2-1-.7-1-.7-.6.6-1.9 1-2.7 1.1-1.7 4.5-5.5 7.3-2 13.5 3.6 6.4 6.2 7.3 1.2 11.7 0 0 3.2.9 4-1.9 0 0-.1 3 .6 3.8.8-.8.6-3.9.6-3.9.7 2.8 4 1.9 4 1.9-5-4.4-2.4-5.3 1.2-11.7 3.4-6.2-.4-9-2.1-13.5zm1 9.3c0 .1-.1.2-.2.4-.5.8-1.4.9-2.1.6-.4-.1-.5-.2-.6-.3l-.2-.2v2.1l.2-.2.3.4c.1.1.2.3.3.6.2.6.1 1.5-.6 2.1-.1.1-.2.1-.4.2-.1.4-.4.9-1.2 1.3l-.2.1-.2-.1c-.8-.4-1.1-.9-1.2-1.3-.1 0-.2-.1-.4-.2-.8-.5-.9-1.4-.6-2.1.1-.4.2-.5.3-.6l.3-.4.2.2v-2.1l-.2.2c-.1.1-.3.2-.6.3-.6.2-1.5.1-2.1-.6-.1-.1-.1-.2-.2-.4-.4-.1-.9-.4-1.3-1.2l-.1-.2.1-.2c.4-.8.9-1.1 1.3-1.2 0-.1.1-.2.2-.4.5-.8 1.4-.9 2.1-.6.2.1.4.2.5.2l-.2-.2c-.1-.1-.2-.3-.3-.6-.2-.6-.1-1.5.6-2.1.1-.1.2-.1.4-.2.1-.4.4-.9 1.2-1.3l.2-.1.2.1c.8.4 1.1.9 1.2 1.3.1 0 .2.1.4.2.8.5.9 1.4.6 2.1-.1.4-.2.5-.3.6l-.1.2c.1-.1.2-.1.5-.2.6-.2 1.5-.1 2.1.6.1.1.1.2.2.4.4.1.9.4 1.3 1.2l.1.2-.1.2c-.5.8-1 1.1-1.4 1.2z"></path>') + ('<path  class="eagle" style="' + e.eagle + '" d="M208.7 89.8c.1-.2.1-.4-.1-.7-.3-.4-.7-.3-.8-.3h-.1l.1.1s.1.1.1.2 0 .3-.3.5c-.1.1-.5.1-.6.1h-1.5v-2.2c0-.1 0-.5.1-.6.2-.2.4-.3.5-.3.1 0 .2.1.2.1l.1.1v-.1c.1-.2.1-.6-.3-.8-.3-.2-.5-.1-.7-.1.2-.6-.5-1.1-.5-1.1s-.6.5-.5 1.1c-.2-.1-.4-.1-.7.1-.4.3-.3.7-.3.8v.1l.1-.1s.1-.1.2-.1.3 0 .5.3c.1.1.1.4.1.6v2.2h-1.6c-.1 0-.5 0-.6-.1-.2-.2-.3-.4-.2-.5 0-.1.1-.2.1-.2l.1-.1h-.1c-.2-.1-.6-.1-.8.3-.2.3-.1.5-.1.7-.6-.2-1.1.5-1.1.5s.5.6 1.1.5c-.1.2-.1.4.1.7.3.4.7.3.8.3h.1l-.1-.1s-.1-.1-.1-.2 0-.3.2-.5c.1-.1.4-.1.6-.1h1.6v4c0 .1 0 .4-.1.6-.2.2-.4.3-.5.3-.1 0-.2-.1-.2-.1l-.1-.1v.1c-.1.2-.1.6.3.8.3.2.5.1.7.1-.2.6.5 1.1.5 1.1s.6-.5.5-1.1c.2.1.4.1.7-.1.4-.3.3-.7.3-.8v-.1l-.1.1s-.1.1-.2.1-.3 0-.5-.3c-.1-.1-.1-.5-.1-.6v-4h1.5c.1 0 .4 0 .6.1.2.2.3.4.3.5 0 .1-.1.2-.1.2l-.1.1h.1c.2.1.6.1.8-.3.2-.3.1-.5.1-.7.6.2 1.1-.5 1.1-.5s-.4-.6-1.1-.5z"></path>') + "</g>" + ('<path  class="shieldheader" style="' + e.shieldheader + '" d="M176.5 52.5v16.1h56.4V52.5h-56.4zm12.1 10.9l-2.5-.2s-.2.8-.2 1.8c0 .7.4.9.6 1h-1.7c.2-.1.6-.3.6-1 .1-1-.2-1.8-.2-1.8l-2.5.2.5-.8-2.6-2.4.7-.2-.4-1.7 1.6.3.3-.8 1.1 1.3-.3-3 .9.8 1.1-2.1 1.1 2.1.9-.8-.3 3 1.1-1.3.3.8 1.6-.3-.4 1.7.7.2-2.6 2.4.6.8zm26.1 2.9h-8.1s-.6-1.3-1.8-1.3c-1.2 0-1.8 1.3-1.8 1.3h-8V57h1.6v-1.4h1.2s1.8.1 2.7-.3c.9-.4 3.3-1.2 4.4.4 1.1-1.6 3.4-.8 4.4-.4.9.4 2.7.3 2.7.3h1.2V57h1.6v9.3zm11.8-2.9l-2.5-.2s-.3.8-.2 1.8c0 .7.4.9.6 1h-1.7c.2-.1.6-.3.6-1 0-1-.2-1.8-.2-1.8l-2.5.2.5-.8-2.6-2.4.7-.2-.4-1.7 1.6.3.3-.8 1.1 1.3-.3-3 .9.8 1.1-2.1 1.1 2.1.9-.8-.3 3 1.1-1.3.3.8 1.6-.3-.4 1.7.7.2-2.6 2.4.6.8z" id="bookspinetop"></path>') + ('<path  class="bookbg" style="' + e.bookspine + '" d="M213.8 57h-.7v7.9h-3c-1-.1-4.1-2-5.2-.8-1.1-1.2-4.2.7-5.2.8-.5.1-3 0-3 0V57H195v9.3h8.1s.6-1.3 1.8-1.3c1.2 0 1.8 1.3 1.8 1.3h8.1V57h-1z" id="bookbgtop"></path>') + '<g id="bookoutlinetop">' + ('<path  class="bookoutline" style="' + e.shieldbg + '" d="M211.9 55.6s-1.8.1-2.7-.3c-.8-.3-2.6-.9-3.8-.2v1.2l.1-.1c.7-1 2.2-.6 3.4-.1 1 .4 2.8.4 3 .3h.4V64.1h-2.1c-.2 0-.7-.2-1.1-.4h-.1c-1.1-.4-2.4-.9-3.6-.8v.9c1.4-.4 3.8 1 4.7 1.1.5.1 3 0 3 0v-9.3h-1.2zM200.6 63.7c-.4.2-.9.4-1.1.4h-2.1V56.4h.4c.1 0 1.9.1 3-.3 1.2-.5 2.7-.8 3.4.1 0 0 0 .1.1.1v-1.2c-1.2-.8-3-.2-3.8.2-.9.4-2.7.3-2.7.3h-1.2v9.3h3c.9-.1 3.3-1.5 4.6-1.1V63c-1.1-.3-2.5.3-3.6.7z"></path>') + "</g>" + ('<path  class="bookspine" style="' + e.bookspine + '" d="M205.4 57v-1.9c-.2.1-.4.3-.6.6-.2-.3-.4-.4-.6-.6V63.7l.6.3c.2-.2.4-.3.6-.3V57z" id="bookspine_1_top"></path>') + '<g id="bookstop">' + ('<path  class="books" style="' + e.books + '" d="M200.8 56c-1.1.4-2.9.4-3 .3h-.4v7.8h2.1c.2 0 .7-.2 1.1-.4 1.1-.4 2.5-.9 3.6-.8V56.3c0-.1-.1-.1-.1-.1-.6-1-2.1-.6-3.3-.2zM211.9 56.4c-.2 0-2 .1-3-.3-1.2-.5-2.7-.8-3.4.1l-.1.1V62.9c1.1-.2 2.5.3 3.6.8h.1c.4.2.9.4 1.1.4h2.1V56.4h-.4z"></path>') + '</g><g id="leavestop"><g id="leafstop">' + ('<path  class="leaves" style="' + e.shieldbg + '" d="M189.9 60l.4-1.7-1.6.3-.3-.8-1.1 1.3.3-3-.9.8-1.1-2.1-1.1 2.1-.9-.8.3 3-1.1-1.3-.3.8-1.6-.3.4 1.7-.7.2 2.6 2.4-.5.8 2.5-.2s.3.8.2 1.8c0 .7-.4.9-.6 1h1.7c-.2-.1-.6-.3-.6-1 0-1 .2-1.8.2-1.8l2.5.2-.5-.8 2.6-2.4-.8-.2zM226.5 63.4l-.5-.8 2.6-2.4-.7-.2.4-1.7-1.6.3-.3-.8-1.1 1.3.3-3-.9.8-1.1-2.1-1.1 2.1-.9-.8.3 3-1.1-1.3-.3.8-1.6-.3.4 1.7-.7.2 2.6 2.4-.5.8 2.5-.2s.2.8.2 1.8c0 .7-.4.9-.6 1h1.7c-.2-.1-.6-.3-.6-1-.1-1 .2-1.8.2-1.8l2.4.2z"></path>') + "</g></g></svg>"),
                this.SVGLogo);
            },
        }, {
            key: "getFooterLogo",
            value: function(c, e) {
                var t = "";
                return ((t = "min-width: 200px; max-width: 425px; height: auto; margin-top: 5px;"),
                1 == c && (t = "min-width: 200px; max-width: 425px; height: auto; margin: 10px;"),
                (this.SVGLogo = '<svg id="mcmaster-logo-footer" style="' + t + '" xmlns="https://www.w3.org/2000/svg" viewBox="0 0 527.6 155.4">' + ('<g id="letters" style="' + e.logoLetters + '">') + '<path class="letters" d="M45.2 65.4H45c-.8 0-1.4-.1-1.9-.7-.6-.8-.6-3.3-.5-4.3V31.5c0-1.1-.1-3.1.4-3.8.2-.2 1-.1 1.7-.1h.4c1.9 0 2-1.3 2-1.7 0-.5-.1-.8-.4-1.1-.4-.4-1-.3-1.5-.3h-7c-.7 0-1.7 0-2.2 1.3L24.2 56.2l-9.7-27.3c-.4-1.2-.6-1.7-.7-1.9 0-.1-.1-.3-.1-.4v-.1c-.3-.9-.6-2-2-2H4.4c-.4 0-1.1-.1-1.5.3-.3.3-.4.6-.4 1.1 0 .4.1 1.7 2 1.7 1.3 0 2.1.1 2.4.4.3.4.3 1.3.2 2.9 0 .3-1.9 29.7-1.9 29.8-.2 3.5-.4 4.7-3.1 4.7-1.9 0-2.1 1-2.1 1.5s.2 1.4 1.5 1.4c.9 0 1.8-.1 2.7-.1.9-.1 1.8-.1 2.7-.1s1.8.1 2.7.1c.9.1 1.8.1 2.7.1.5 0 1.9 0 1.9-1.4 0-.4-.1-.7-.4-.9-.5-.5-1.4-.5-1.9-.5h-.1c-1.2 0-2-.3-2.5-.8-1.1-1.1-1-3.4-.9-6.3l1.6-26L20.9 64c.2.6.3.8.4 1v.1c.1.5.4 1.7 1.4 1.7.9 0 1.2-.9 1.4-1.4 0-.1 0-.1.1-.2l12.5-33.5v28.9c0 1.2 0 3.3-.7 4-.5.5-1.7.8-2.4.8h-.2c-.5 0-1.3 0-1.9.5-.3.3-.4.6-.4 1 0 .5.2 1.4 1.7 1.4 1.2 0 2.4-.1 3.5-.1 1.2-.1 2.4-.1 3.6-.1 1 0 1.9.1 2.9.1.9.1 1.9.1 2.9.1 1.5 0 1.7-.9 1.7-1.4 0-.4-.1-.7-.4-1-.4-.5-1.3-.5-1.8-.5z"></path><path class="letters" d="M60.2 69.1c3.6 0 6.9-1.2 9.6-3.6 1.8-1.7 2.1-2.5 2.1-2.9 0-.6-.5-1.1-1-1.1s-.9.4-1.3.9c0 .1-.1.1-.1.1-1.8 1.9-4.1 2.9-6.9 2.9-7 0-11.3-7.2-11.3-13.9 0-4.2 1.6-8.3 4.4-10.9 1.4-1.4 3.9-2.7 6-2.7 2.8 0 4.3 2.7 5.6 4.9.9 1.6 1.6 2.8 2.7 2.8.3 0 .6-.1.8-.4.6-.7.6-2.1.5-3.5V40.8c.1-1 .1-2.3-.8-2.9-2.2-1.7-5.7-2.4-8.1-2.4-9.2 0-17 8-17 17.5.2 8.6 6.9 16.1 14.8 16.1z"></path><path class="letters" d="M95.5 65.2c0-.1 0-.1 0 0l12.7-33.5v28.9c0 1.2 0 3.3-.7 4-.5.5-1.7.8-2.4.8h-.2c-.5 0-1.3 0-1.9.5-.3.3-.4.6-.4 1 0 .5.2 1.4 1.7 1.4 1.2 0 2.4-.1 3.5-.1 1.2-.1 2.4-.1 3.6-.1 1 0 1.9.1 2.9.1.9.1 1.9.1 2.9.1 1.5 0 1.7-.9 1.7-1.4 0-.4-.1-.7-.4-1-.5-.5-1.3-.5-1.9-.5h-.2c-.8 0-1.4-.1-1.9-.7-.6-.8-.6-3.3-.5-4.3V31.5c0-1.1-.1-3.1.4-3.8.3-.4 1.1-.4 1.7-.3h.4c1.9 0 2-1.3 2-1.7 0-.5-.1-.8-.4-1.1-.4-.4-1.1-.4-1.6-.3h-7c-.7 0-1.7 0-2.2 1.3L95.7 56.2 85.7 28c-.2-.6-.3-.9-.4-1 0-.2-.1-.3-.1-.5-.3-.9-.6-2-2-2h-7.3c-.5 0-1.1-.1-1.6.3-.2.3-.3.6-.3 1.1 0 .4.1 1.7 2 1.7 1.3 0 2.1.1 2.4.4.3.4.3 1.3.2 2.9-1.8 29.6-1.9 29.8-1.9 29.8-.2 3.5-.4 4.7-3.1 4.7-1.9 0-2.1 1-2.1 1.5s.2 1.4 1.5 1.4c.9 0 1.8-.1 2.7-.1.9-.1 1.8-.1 2.7-.1.9 0 1.8.1 2.7.1.9.1 1.8.1 2.7.1.5 0 1.9 0 1.9-1.4 0-.4-.1-.7-.4-.9-.5-.5-1.4-.5-1.9-.5h-.1c-1.2 0-2-.3-2.5-.8-1.1-1.1-1-3.4-.9-6.3l1.6-25.9 10.8 31.4c.2.7.4 1 .4 1.2v.1c.1.5.4 1.7 1.4 1.7.9-.2 1.2-1.1 1.4-1.7z"></path><path class="letters" d="M135.3 64.8c.6 1.5 1.6 3.9 4 3.9 1.8 0 3.6-1.2 4.9-2.2l.1-.1c.6-.5 1.6-1.5 1.6-2.5 0-.6-.5-1.1-1-1.1s-.8.4-1.1.7c-.4.5-1 1-1.7 1-.3 0-.5-.1-.7-.3-.9-.9-.9-3.5-.9-4.6V42.2c0-1.7.1-3.4-1.4-4.8-1.3-1.3-3.4-2-6.2-2-4.1 0-8.7 1.9-11.8 5-1.3 1.2-2.8 3.4-2.8 5.4 0 .9.5 1.4 1.4 1.4s2.3-.6 2.9-1c1.1-.5 1.5-1.5 1.9-2.5l.1-.3c1.6-3.9 3.6-5.5 6.8-5.5s3.5 1.8 3.5 5.7v3.1c0 2.4 0 2.4-2.1 3.4 0 0-1.7.9-3 1.6-1 .5-1.9 1-1.9 1l-.4.2c-3.7 2-9.2 5-9.2 10.1 0 4 3.3 6.1 6.5 6.1 4.4 0 7.9-3.2 9.6-4.7.2-.2.4-.4.6-.5.1.2.2.6.3.9zm-6.5-9.7c.1-.1.4-.2.9-.5l4.9-2.7c.1 0 .2-.1.3-.1h.1c0 .2.1.5 0 1.1v4.4c0 2.2-.1 3.3-1.4 4.9-1.5 1.6-3.5 2.6-5.5 2.6-1.8 0-3.8-.9-3.8-3.6-.2-3.1 2-4.8 4.5-6.1zm30.6-6.9c-3.5-1.3-6.6-2.5-6.6-5.9 0-3 3.1-4.6 5.3-4.6 4.2 0 5.3 2.7 6 4.6.4 1.1.8 2 1.7 2 .3 0 .6-.1.8-.3.6-.7.5-2.1.4-3.4V39.7c.1-1 .2-2.4-1.1-3-1.6-.7-5.1-1.2-6.8-1.2-3.2 0-5.8.8-7.8 2.4-2.3 1.9-3.6 4.3-3.6 7 0 5.8 5.5 7.8 9.5 9.2.3.1.5.2.6.2 2.8 1 5.7 2.4 5.7 6.2 0 4.1-3.7 6.3-7.2 6.3-5.2 0-6-3.8-6.5-6.6-.3-1.6-.6-3-1.8-3s-1.3 1.4-1.4 2v.1s0 .6-.2 3.8v1.3c0 1 0 2.1 1.2 2.7 2.3 1.3 6.2 2.2 8.3 2.2 5.2 0 12.6-3.4 12.6-10.8.2-6.8-4.7-8.7-9.1-10.3zm26 14.6c-.4 0-.7.3-1.2.7-.8.7-2 1.7-3.4 1.7-.7 0-1.3-.2-1.8-.7-1.4-1.4-1.4-4.7-1.4-6.8v-18c0-.7.1-.9.2-.9.1-.1.5-.1.9-.1h4.9c.6 0 1.1.1 1.4-.3.4-.3.4-.9.4-1.4s0-1.5-1.1-1.5H178c-.4 0-.5 0-.5-.8v-5c0-1.2-.7-1.4-1.1-1.4-.7 0-1 .7-1.2 1-1.4 3.2-3.1 4.9-5.9 6.9l-.1.1c-.3.3-.8.7-.8 1.3 0 .3.1.6.3.8.5.4 1.3.4 2 .4h1.1c0 .1.1.2.1.7v19.1c0 2.7-.1 5.9 1.5 8.1 1.1 1.5 3 2.4 5 2.4 2.3 0 4.5-1 6.3-2.8.4-.3 1.5-1.4 1.5-2.4.2-.5-.2-1.1-.8-1.1z"></path><path class="letters" d="M193.3 49.1h19.5c.3 0 1.3-.1 1.3-1.8 0-2.4-1-5.5-2.3-7.4-2.1-2.9-5.6-4.6-9.6-4.6-4.4 0-8.5 1.7-11.8 4.8-3.2 3.1-4.7 6.9-4.7 12.1 0 9.4 6.6 16.7 14.9 16.7 4.2 0 7.4-1.3 10.4-4.1 1.8-1.7 2.6-2.8 2.6-3.5 0-.6-.5-1.1-1.1-1.1-.5 0-.8.3-1.4 1-1.3 1.3-3.6 3.6-7.9 3.6-7.7 0-11.7-7.1-11.7-14.1 0-.8.1-1.3.2-1.4.4-.2.9-.2 1.6-.2zm.3-6.9c1.8-2.8 4.7-4.4 7.7-4.4 1.5 0 3.7.3 5.1 2 .9 1.1 1.5 2.6 1.5 3.8 0 1.2-.6 1.9-1.9 2.2-1.8.5-5.3.5-7.2.5h-5.5c-.4 0-1 0-1.2-.1 0 0-.1-.1-.1-.2.1-1 1.1-3 1.6-3.8zm38.4-6.5c-3.4 0-5.7 3.1-7 4.8-.1.1-.2.2-.2.3V37c0-.3 0-.9-.3-1.2-.1-.1-.4-.3-.8-.3-.7 0-1.1.5-1.4.9l.1.1-.1-.1-.2.2c-1 1.3-3.6 3-5 3.5-.1 0-.2.1-.2.1-.6.2-1.6.5-1.6 1.6 0 .7.5 1.1 1.3 1.1h.8c.7 0 1.2.1 1.4.4.3.4.5 1.7.5 3.9v14.6c.1 2.6 0 3.8-2.4 4h-.3c-.6 0-2 .1-2 1.5 0 .8.6 1.3 1.5 1.3 1 0 2-.1 3-.1 1-.1 2-.1 3-.1.9 0 1.9 0 2.8.1 1 .1 2 .1 3.1.1.8 0 1.3-.5 1.3-1.3 0-1.3-1.4-1.4-2-1.5h-.3c-2.3-.2-2.4-1.4-2.4-4V49.1c0-2.6 0-4.3 1.3-6.4.7-.9 1.6-2.3 2.8-2.3.5 0 .8.4 1.4 1 .6.7 1.3 1.7 2.7 1.7 1.9 0 3.2-1.4 3.2-3.4.2-2.3-1.6-4-4-4zM24.6 75.5c-.5 0-1 0-1.5.1-.5 0-.9.1-1.4.1s-1.1 0-1.6-.1c-.6 0-1.1-.1-1.7-.1-.4 0-.8.1-1 .4-.2.2-.3.5-.3.8 0 .4.2.6.3.7.4.4.9.4 1.2.4h.1c.8 0 1.4 0 1.7.6.3.6.3 2.8.3 3.6v11.6c0 1.9 0 3.6-1.2 4.9-1.6 1.8-4.1 2-5.5 2-1 0-4.3-.2-5.4-2.4-.7-1.3-.7-3.9-.7-5.6V80.1c0-1 0-1.7.2-2 .2-.2.7-.3 1.6-.3 1.3 0 1.5-.6 1.5-1.1 0-.7-.5-1.1-1.2-1.1s-1.4 0-2.1.1c-.7 0-1.4.1-2.1.1s-1.3 0-2-.1c-.6 0-1.4-.1-2.1-.1-.4 0-.7.1-.9.3s-.3.5-.3.8c0 .5.3 1.1 1.5 1.1.9 0 1.4.1 1.6.3.3.3.3 1 .2 2v13.6c0 2.7 0 5.2 2.4 7 2.1 1.7 5.4 2 7.2 2 3.3 0 5.7-.8 7.3-2.3 2.2-2.1 2.2-4.3 2.2-6.9V79.9c0-1.7.1-2.2 1.3-2.2 1.4 0 1.7-.6 1.7-1.1 0-.2-.1-1.1-1.3-1.1zm20.5 24.7h-.2c-1.1-.1-1.2-.5-1.2-2.1v-7.5c0-1.9 0-3.9-1.2-5.6-1.1-1.6-2.7-2.4-4.8-2.4-2.6 0-4.4 1.7-5.5 2.7v-1.6c0-.3 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6 0 0-.1.1-.1.2-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1v8.5c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1s1-.4 1-1c0-1-1-1.1-1.4-1.1h-.1c-1.1-.1-1.2-.5-1.2-2.1v-7.6c0-1.6.1-2.3 1-3.4.9-1 2-1.6 3.2-1.6 1.3 0 2.4.6 3 1.6s.6 2.5.6 3.8v7.2c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.7-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1s1-.4 1-1c.6-1-.5-1.1-.8-1.1zm10.5 0h-.2c-1.1-.1-1.2-.5-1.2-2.1V83.7c0-.2 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6l-.1.1c-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1V98c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1s1-.4 1-1c.3-.9-.7-1-1.1-1zm-5.3-22.6c0 1.5.9 2.5 2.1 2.5 1.3 0 2.2-1 2.2-2.6 0-1.2-.8-2.5-2.1-2.5-1.2 0-2.2 1.1-2.2 2.6zm26.2 5.6c-.2-.2-.5-.2-.7-.2h-5.5c-.9 0-1.1.5-1.1.9 0 .7.5 1 1.6 1 .3 0 .9.1.9.5 0 .3-.2.9-.4 1.3 0 .1-.1.2-.1.3-.1.1-.2.5-.5 1.1l-3.3 8.1c-3.2-8.7-3.3-8.9-3.3-8.9l-.1-.1c-.1-.4-.5-1.3-.5-1.7 0-.6.7-.6.8-.6h.1c.3 0 .9 0 1.2-.3.2-.2.3-.4.3-.6 0-.3-.1-.6-.3-.7-.3-.3-.7-.3-.9-.3h-6.8c-.2 0-.5 0-.8.2 0 .3-.1.5-.1.8s.1.6.3.8c.2.2.5.2.9.2 1.1.1 1.2.4 1.7 1.7l.1.3c2 5.4 5.3 14.3 5.3 14.4l.2.5c.1.5.5.8.9.8.6 0 .9-.7 1.1-1.1v-.1l-.1-.1h.1s5.2-12.6 5.3-12.7c.1-.2.2-.4.2-.6.5-1.4 1.1-2.9 2.3-3.1h.1c.3 0 1.3-.1 1.3-1.1.1-.1.1-.4-.2-.7zm4.8 7.8h11.3c.2 0 1-.1 1-1.3 0-1.5-.6-3.3-1.4-4.4-1.3-1.8-3.4-2.8-5.7-2.8-2.6 0-5.1 1-7 2.9-1.9 1.9-2.8 4.1-2.8 7.2 0 5.6 3.9 10 8.9 10 2.5 0 4.4-.8 6.2-2.5 1.4-1.3 1.6-1.9 1.6-2.2 0-.5-.4-.9-.9-.9-.4 0-.6.3-1 .6-.7.7-2 2-4.4 2-4.3 0-6.6-4-6.6-8 0-.5.1-.7.1-.7.1.1.5.1.7.1zm4.7-6.6c.8 0 2 .2 2.8 1.1.5.6.8 1.4.8 2s-.3.9-.9 1.1c-1 .3-3 .3-4.1.3h-3.7c0-.5.5-1.6.8-2 1-1.6 2.6-2.5 4.3-2.5zm19.7-1.6c-1.9 0-3.2 1.5-3.9 2.5v-1.6c0-.2 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6 0 0-.1.1-.1.2-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1v8.5c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1.6 0 1-.4 1-1 0-1-1-1.1-1.4-1.1h-.1c-1.1-.1-1.2-.5-1.2-2.1v-7.3c0-1.5 0-2.4.7-3.6.4-.5.9-1.2 1.4-1.2.2 0 .3.1.6.5s.8 1.1 1.8 1.1c1.2 0 2.1-.9 2.1-2.2.1-1.5-1-2.6-2.5-2.6zm11.5 7.2c-2-.7-3.7-1.4-3.7-3.2 0-1.6 1.7-2.5 2.8-2.5 2.3 0 2.9 1.4 3.3 2.5.3.6.5 1.3 1.2 1.3.2 0 .5-.1.6-.3.4-.5.4-1.3.3-2.2v-.5c0-.6.1-1.6-.8-2-1-.5-3-.7-4-.7-1.9 0-3.5.5-4.7 1.5-1.4 1.1-2.2 2.6-2.2 4.2 0 3.6 3.3 4.7 5.7 5.6l.3.1c2 .7 3.2 1.5 3.2 3.4 0 2.2-2 3.4-3.9 3.4-2.8 0-3.2-1.9-3.5-3.6-.2-1-.4-2-1.3-2s-1 1-1 1.3v.1l-.1 2.8v.2c0 .6 0 1.4.8 1.8 1.4.8 3.7 1.3 5 1.3 3.7 0 7.6-2.4 7.6-6.5 0-3.9-3-5-5.6-6zm14.6-12.5c0-1.2-.8-2.5-2.1-2.5-1.2 0-2.2 1.1-2.2 2.6s.9 2.5 2.1 2.5c1.4 0 2.2-1 2.2-2.6zm1 22.7h-.2c-1.1-.1-1.2-.5-1.2-2.1V83.7c0-.3 0-.6-.3-.9-.1-.1-.3-.2-.6-.2-.5 0-.8.4-1 .6 0 0-.1.1-.1.2-.5.7-2 1.7-2.8 1.9h-.1c-.4.1-1.1.4-1.1 1.2 0 .5.4.9 1 .9h.5c.4 0 .6.1.6.1.1.1.2.4.2 2.1v8.5c0 1.6-.1 2-1.2 2.1h-.2c-.3 0-1.4.1-1.4 1.1 0 .5.3 1 1.1 1 .6 0 1.2 0 1.8-.1.6 0 1.1-.1 1.7-.1.5 0 1.1 0 1.6.1.6 0 1.2.1 1.8.1s1-.4 1-1c.3-1-.7-1.1-1.1-1.1zm11.6-1.7c-.3 0-.5.2-.9.5-.4.4-1.1 1-1.8 1-.4 0-.6-.1-.9-.3-.7-.7-.7-2.6-.7-3.8v-11h3.3c.4 0 .7 0 1-.2.3-.3.3-.6.3-1 0-.8-.3-1.1-.9-1.1h-3.7v-3.1c0-1-.7-1.1-.9-1.1-.4 0-.7.2-.9.7-.8 1.8-1.8 2.8-3.3 3.9l-.1.1c-.2.2-.6.5-.6 1 0 .2.1.5.3.6.4.3.9.3 1.4.3h.4v11.4c0 1.6 0 3.5.9 4.8.7.9 1.8 1.5 3.1 1.5 1.4 0 2.7-.6 3.8-1.7.3-.3.9-.9.9-1.6.1-.4-.2-.9-.7-.9zM164.5 83h-5.8c-.6 0-1.1.5-1.1 1.1 0 .9 1 .9 1.4.9 1.4 0 1.4.7 1.4.9 0 .4-.3 1-.4 1.4v.1c0 .1-2.4 6.3-3.6 9.3l-3.6-9.6V87c-.2-.4-.4-1-.4-1.4 0-.7 1.2-.7 1.3-.7 1.2 0 1.5-.5 1.5-.9 0-.7-.5-1.1-1.1-1.1H147c-.7 0-1.3.4-1.3 1.1 0 .9 1.1.9 1.5.9.8 0 1.2.8 1.6 2.1 0 0 .1.3.2.4l4.8 12.7c0 .1.1.3.2.4.1.4.3.8.3 1.1 0 .3-.1.5-.2.8 0 .1-.1.2-.1.2-1 2.5-1.2 3.1-1.2 3.2s-.1.2-.1.2v.1c-.2.4-.3.8-.5.8-.3.1-.8.1-1.2.1h-.3c-1.7 0-1.7 1.6-1.7 2.2s.2 1 .5 1.3c.5.5 1.3.6 2 .6h.2c1.7 0 1.9-.6 2.3-1.9v-.1l6.2-16.4c.8-2.1 1.1-2.8 1.1-3.1.3-.8 1.3-3.3 1.9-4.2.3-.4.9-.7 1.2-.7h.2c.4 0 1.1-.1 1.1-.8-.1-.4-.6-.9-1.2-.9z"></path></g>' + ('<path id="shieldoutline" style="fill:' + e.shieldoutline + '" class="st1" d="M234.8 74.1H174v46.1c1 11 12 29.3 30.2 34.9l.3.1.3.1.3.1.3-.1.3-.1.3-.1c18.2-5.6 29.2-24 30.2-35.2V74.3h-1.4v-.2zm-.5 1.9v44c-.9 10.7-11.6 28.3-29.2 33.8l-.3.1h-.2l-.3-.1c-17.6-5.4-28.3-23.1-29.2-33.7V75.5H234v.5h.3z"></path>') + ('<path id="shield" style="' + e.shield + '" class="st2" d="M232.9 75.6h-57.6v44.6c.9 10.6 11.6 28.2 29.2 33.7l.3.1h.2l.3-.1c17.6-5.4 28.2-23.1 29.2-33.8V75.7l-1.6-.1zm0 44.5c-.8 9.3-10.5 27-28.2 32.5-17.7-5.5-27.4-23.2-28.2-32.5v-27h56.3l.1 27zm0-27h-56.4V77h56.4v16.1z"></path>') + ('<g id="shieldbg" style="' + e.shieldbg + '">') + '<path class="shieldbg" d="M204.8 93.1h-28.2v27c.8 9.3 10.5 27 28.2 32.5 17.7-5.5 27.4-23.2 28.2-32.5v-27h-28.2zm11.5 5.9s2.6 4.7.2 6.5c0 0 1.5-.2 2.8.5 0 0-.9 1.6-1.8 2.1 0 0 1.9.9 2.4 1.6 0 0-1.2 1-2.8 1.2 0 0 1.7 1.1 2.2 2 0 0-1.3.9-2.9.6 0 0 1.8 1.2 1.9 2.5 0 0-1.8.5-3.1-1 0 0 1.2 2 .5 3.3-.2.4-.7.8-.7.8-1.1-.6-1.3-.6-1.4-1.8 0-.6.1-.7.1-2 0-1.1-.2-2.1-.2-2.1s2.4-.4 1.8-4.6c0 0-3.2 2.2-3.6-.8-.5-3.6 5-1.7 4.6-8.8zm-2.9 35s-.1 0-.2.1c-.3.1-.5.4-.4 1.1 0 0-1-1.1.4-1.9l.1-.1c0 .1-.2.5.1.8zm-2-6.5s.3.8.4 1c.7 1.5-.3 3.6-.3 3.6.5-2.8-2.4-5.3-2.4-5.3.4-1.3 1.8-3.3 1.9-3.4 0 .1.1.4.8 1.5 2 3.2 3.8 3 3.8 3-1.7.8-4.2-.4-4.2-.4zm-.6-7.1c-3.6 6.4-6.2 7.3-1.2 11.7 0 0-3.2.9-4-1.9 0 0 .2 3.1-.6 3.9-.8-.8-.6-3.8-.6-3.8-.7 2.8-4 1.9-4 1.9 5-4.4 2.4-5.3-1.2-11.7-3.5-6.2.3-8.9 2-13.5.8-.1 2.1-.4 2.7-1.1 0 0 .3.5 1 .7.7-.2 1.1-.7 1.1-.7.5.6 2 1 2.7 1 1.8 4.6 5.6 7.4 2.1 13.5zm-12.1 11.7s-1-2-.3-3.6c.1-.1.4-1 .4-1s-2.5 1.2-4.2.3c0 0 1.8.2 3.8-3 .7-1.2.8-1.5.8-1.5.1.2 1.5 2.1 1.9 3.4 0 0-3 2.6-2.4 5.4zm-1.9 2.1c-.1 0-.2-.1-.2-.1.2-.3.1-.7.1-.7.1 0 .1.1.1.1 1.4.8.4 1.9.4 1.9.1-.9-.2-1.1-.4-1.2zm1.2-34.3c0 .3.4.9.7 1.1.5.4 4.7.1 5.2.1-.4-.8-2.3-2.3-3.3-2.2-1.1 0-1.4 1.1-1.4 1.1-.5-.5-.6-1.4.1-2.1.6-.6 3.5-.8 3.7-1 .1-.2.3-.6 1-.5s1.3 1.2 3.2.8c0 0 1.5-.1 1.2-1-.1-.4-1-.4-1-.4s1.9-.3 1.7 1.2c-.1 1.1-1.8 1-1.9 2.9 0 .3-.1 4.1 1.9 5.6 0 0-2.5-.2-3.5-2.8 0 0 0 1.9-.6 1.9s-.8-1.9-.8-1.9c-.2 2.5-3.1 2.3-3.1 2.3 2-.3 1.4-1.3 1.2-1.6-.3-.5-1.1-.2-1.4-.2-1.3.4-1.2-.5-1.2-.5h3.3c.9-.1.8-.9.9-1.2-.4 0-4.5.1-4.8.1s-.5 0-1-.3c-.4-.3-.1-1.4-.1-1.4zm-4.2-.9c-.4 7.1 5.1 5.3 4.7 8.9-.4 3-3.6.8-3.6.8-.6 4.2 1.8 4.6 1.8 4.6s-.1 1-.2 2.1c0 1.3.1 1.4.1 2-.1 1.2-.3 1.3-1.4 1.8 0 0-.4-.4-.7-.8-.7-1.3.5-3.3.5-3.3-1.3 1.6-3.1 1-3.1 1 .1-1.3 1.9-2.5 1.9-2.5-1.6.3-2.9-.6-2.9-.6.5-.9 2.2-2 2.2-2-1.7-.1-2.8-1.2-2.8-1.2.5-.7 2.4-1.6 2.4-1.6-.9-.5-1.8-2.1-1.8-2.1 1.3-.7 2.8-.5 2.8-.5-2.5-1.9.1-6.6.1-6.6zm-11.1 24.5s5.7 1.8 8-4c-3.8 3-6.3 2.7-7.4 2.2-1.5-.7-1.8-3-1.8-3 2.5 1.2 6.3-.7 8.3-3.1-5.3.8-7.5-.7-8.1-1.6-.9-1.4-1.7-3.8-1.7-3.8 1.4 1.4 6.2 3 8.9 1.5-5.5-2.7-7.9-3.6-8.4-4.9-.6-1.6-.6-4.2-.6-4.2 1 1.8 5.7 3.7 9.2 4.2-5.6-3.7-7.9-6.2-8-7.7-.2-1.7.2-4.3.2-4.3 1 2.9 9.6 7.5 9.6 7.5 0 .6-.1 1.2.1 1.8 0 0-1 .3-2.1 1.4 0 0 .5 1.5 1.1 2.3 0 0-1.3 1-1.7 1.9 0 0 .1.7 1.5 1.8 0 0-.4.4-1 1.7 0 0 .9.9 1.9 1.4 0 0-.5 1-.4 2.2 0 0 1.2 1.1 2.5 1.1 0 0 .1.8.9 1.8.3.4 1.4 1.3 1.4 1.3s1.9-.7 2.4-1.3l.1.3s.1.6.8 1.6c0 0-1.4 5.7-8.9 5.9 4.3-1.4 4.6-5.7 4.6-5.7-4.4 4.8-7.1 5.4-8.5 4.7-1.6-.7-2.9-3-2.9-3zm3.7 11.9s-1.5-1.4.2-2.8c0 0-.2.4.2 1-.1.1-1.1.5-.4 1.8zm.3-5.7s.2-1.5 1.9-.9c0 0-.4.2-.5.6 0 0-.9-.6-1.4.3zm2 7.6s0 .5.5.9c0 0-.8.7.3 1.7 0 0-2-.8-.8-2.6zm5.6-3.4c-.4-.3-1.2-.1-1.4 0-.5.2-.9.9-1.1 2.2-.3 1.7-1.6 1.9-2 1.5-1.3-1.3.6-2.5.9-2.7 1.1-.9 1-1.4.8-1.6-.3-.5-1.6-.5-2.5.2-.8.7-2.1.2-1.7-1 .3-1 1.7-.5 2-.5.2 0 .5.1.7-.2s-.3-.7-.6-.8c-.5-.2-1-.8-.6-1.3.5-.6 1.4-.2 1.4.7 0 .4.2 1.2.7 1.5 1.6.7 3.7-2 3.7-2s.9.3 2 .2c0 0-.5 1.3-2.8 2.4-.5.3-.4.6-.1.8 0 0 .5.1.8 0 .5-.2 1.2-.4 1.4.4s-.7 1.3-1.4.8c.2-.3-.1-.5-.2-.6zm2.3 9.6c-3.7-4.2-.9-7 1.8-8.1 1.8-.8 1.7-1.3 1.7-1.3s2 .6 3.2-.1c0 0-.3.9-.9 1.8-3 4-5 2-5 2-2.4 1-.8 5.7-.8 5.7zm14.8.3c-1.1.9-2-1.6-2-1.6s-.1 2.3-2.1 2.4c0 0 3-1.8-.1-5.9.3 2.9-.7 5.6-2.1 5.6-1.4 0-2.4-2.7-2.1-5.6-3.1 4.1-.1 5.9-.1 5.9-2 0-2.1-2.4-2.1-2.4s-.9 2.5-2 1.6c-1.7-1.4 1.3-2.8 1.3-2.8-1.7-.1-2-1.1-2-1.1 4.4.5 6.3-4.1 6.3-4.1.3.3.5.3.7.4.2-.1.5-.2.7-.4 0 0 1.9 4.6 6.3 4.1 0 0-.3 1-2 1.1 0 .1 3 1.4 1.3 2.8zm2.1-.3s1.5-4.7-.8-5.8c0 0-2.1 2-5-2-.6-.8-.9-1.8-.9-1.8 1.2.8 3.2.1 3.2.1s-.1.6 1.7 1.3c2.7 1.2 5.5 4.1 1.8 8.2zm7.1-3.6c1.1-1 .3-1.7.3-1.7.6-.5.5-.9.5-.9 1.1 1.8-.8 2.6-.8 2.6zm.4-6.5c-.8-.7-2.1-.7-2.5-.2-.1.2-.3.8.8 1.6.4.3 2.3 1.5.9 2.7-.5.4-1.7.3-2-1.5-.2-1.3-.6-1.9-1.1-2.2-.2-.1-1-.3-1.4 0-.1.1-.4.3-.4.3-.7.5-1.6-.1-1.4-.8.2-.9.9-.7 1.4-.4.4.2.8 0 .8 0 .3-.2.4-.5-.1-.8-2.3-1.1-2.8-2.4-2.8-2.4 1.1.1 2-.2 2-.2s2.1 2.8 3.7 2c.5-.2.7-1.1.7-1.5 0-.8.9-1.3 1.4-.7.5.6-.1 1.1-.6 1.3-.3.1-.7.5-.6.8.2.3.4.2.7.2s1.7-.5 2 .5c.7 1.4-.7 2-1.5 1.3zm1-4c-.1-.4-.5-.6-.5-.6 1.7-.6 1.9.9 1.9.9-.6-.9-1.4-.3-1.4-.3zm1.7 6c.7-1.3-.3-1.7-.3-1.7.4-.6.2-1 .2-1 1.6 1.3.1 2.7.1 2.7zm6.4-25.2s-.8 2.3-1.7 3.8c-.6.9-2.8 2.4-8.1 1.6 2 2.4 5.7 4.3 8.3 3.1 0 0-.3 2.3-1.8 3-1.1.5-3.6.8-7.4-2.2 2.3 5.7 8 4 8 4s-1.3 2.3-2.8 3.1c-1.3.7-4 .1-8.5-4.7 0 0 .3 4.3 4.6 5.7-7.6-.2-8.9-5.9-8.9-5.9.7-1.1.8-1.6.8-1.6l.1-.3c.5.5 2.4 1.3 2.4 1.3s1.1-1 1.4-1.3c.7-1.1.9-1.8.9-1.8 1.3 0 2.5-1.1 2.5-1.1.1-1.2-.4-2.2-.4-2.2.9-.4 1.9-1.4 1.9-1.4-.6-1.3-1-1.7-1-1.7 1.5-1.1 1.5-1.8 1.5-1.8-.4-1-1.7-1.9-1.7-1.9.6-.8 1.1-2.3 1.1-2.3-1.1-1.1-2.1-1.4-2.1-1.4.2-.6.1-1.2.1-1.8 0 0 8.7-4.5 9.6-7.5 0 0 .4 2.6.2 4.3-.1 1.5-2.5 3.9-8 7.7 3.4-.5 8.1-2.4 9.2-4.2 0 0 0 2.7-.6 4.2-.5 1.3-2.9 2.2-8.4 4.9 2.7 1.4 7.4-.2 8.8-1.6z"></path><path class="shieldbg" d="M211.1 114.6c-.4-.8-.9-1.1-1.3-1.2-.1-.1-.1-.2-.2-.4-.5-.8-1.4-.9-2.1-.6-.2.1-.4.2-.5.2l.1-.2c.1-.1.2-.3.3-.6.2-.6.1-1.5-.6-2.1-.1-.1-.2-.1-.4-.2-.1-.4-.4-.9-1.2-1.3l-.2-.1-.2.1c-.8.4-1.1.9-1.2 1.3-.1 0-.2.1-.4.2-.8.5-.9 1.4-.6 2.1.1.4.2.5.3.6l.2.2c-.1-.1-.3-.1-.5-.2-.6-.2-1.5-.1-2.1.6-.1.1-.1.2-.2.4-.4.1-.9.4-1.3 1.2l-.1.2.1.2c.4.8.9 1.1 1.3 1.2 0 .1.1.2.2.4.5.8 1.4.9 2.1.6.4-.1.5-.2.6-.3l.2-.2v2.1l-.2-.2-.3.4c-.1.1-.2.3-.3.6-.2.6-.1 1.5.6 2.1.1.1.2.1.4.2.1.4.4.9 1.2 1.3l.2.1.2-.1c.8-.4 1.1-.9 1.2-1.3.1 0 .2-.1.4-.2.8-.5.9-1.4.6-2.1-.1-.4-.2-.5-.3-.6l-.3-.4-.2.2v-2.1l.2.2c.1.1.3.2.6.3.6.2 1.5.1 2.1-.6.1-.1.1-.2.2-.4.4-.1.9-.4 1.3-1.2l.1-.2v-.2zm-1.2.3s-.1 0 0 0c0 .1-.5.7-1.1.5.1.2.1.4-.1.7-.3.4-.7.3-.8.3h-.1l.1-.1s.1-.1.1-.2 0-.3-.3-.5c-.1-.1-.4-.1-.6-.1h-1.5v4c0 .1 0 .5.1.6.2.2.4.3.5.3s.2-.1.2-.1l.1-.1v.1c.1.2.1.6-.3.8-.3.2-.5.1-.7.1.2.6-.5 1.1-.5 1.1s-.6-.5-.5-1.1c-.2.1-.4.1-.7-.1-.4-.3-.3-.7-.3-.8v-.1l.1.1s.1.1.2.1.3 0 .5-.3c.1-.1.1-.4.1-.6v-4h-1.6c-.1 0-.4 0-.6.1-.2.2-.3.4-.2.5 0 .1.1.2.1.2l.1.1h-.1c-.2.1-.6.1-.8-.3-.2-.3-.1-.5-.1-.7-.6.2-1.1-.5-1.1-.5s.5-.6 1.1-.5c-.1-.2-.1-.4.1-.7.3-.4.7-.3.8-.3h.1l-.1.1s-.1.1-.1.2 0 .3.2.5c.1.1.5.1.6.1h1.6v-2.2c0-.1 0-.4-.1-.6-.2-.2-.4-.3-.5-.3s-.2.1-.2.1l-.1.1v-.1c-.1-.2-.1-.6.3-.8.3-.2.5-.1.7-.1-.2-.6.5-1.1.5-1.1s.6.5.5 1.1c.2-.1.4-.1.7.1.4.3.3.7.3.8v.1l-.1-.1s-.1-.1-.2-.1-.3 0-.5.3c-.1.1-.1.5-.1.6v2.2h1.5c.1 0 .5 0 .6-.1.2-.2.3-.4.3-.5s-.1-.2-.1-.2l-.1-.1h.1c.2-.1.6-.1.8.3.2.3.1.5.1.7.6-.2 1 .4 1.1.5zm-5.7-16.4c0-.1 0-.2-.1-.3h.5v-.1l-.1-.5v-.1h-.1l-2.3.9 1.3-.1c0 .1-.1.2-.1.2 0 .3.2.5.5.5.2.1.4-.2.4-.5z"></path></g>' + ('<g id="eagle" style="' + e.eagle + '">') + '<path class="st4" d="M202.4 135.7c.6-.8.9-1.8.9-1.8-1.2.8-3.2.1-3.2.1s.1.6-1.7 1.3c-2.7 1.1-5.5 4-1.8 8.1 0 0-1.5-4.7.8-5.8 0 .1 2.1 2.1 5-1.9zm-8.8-30.3s-1.5-.2-2.8.5c0 0 .9 1.6 1.8 2.1 0 0-1.9.9-2.4 1.6 0 0 1.2 1 2.8 1.2 0 0-1.7 1.1-2.2 2 0 0 1.3.9 2.9.6 0 0-1.8 1.2-1.9 2.5 0 0 1.8.5 3.1-1 0 0-1.2 2-.5 3.3.2.4.7.8.7.8 1.1-.6 1.3-.6 1.4-1.8 0-.6-.1-.7-.1-2 0-1.1.2-2.1.2-2.1s-2.4-.4-1.8-4.6c0 0 3.2 2.2 3.6-.8.4-3.6-5.1-1.8-4.7-8.9.1.2-2.5 4.9-.1 6.6z"></path><path class="st4" d="M194 121.9s-.3 4.3-4.6 5.7c7.6-.2 8.9-5.9 8.9-5.9-.7-1.1-.8-1.6-.8-1.6l-.1-.3c-.5.5-2.4 1.3-2.4 1.3s-1.1-1-1.4-1.3c-.7-1.1-.9-1.8-.9-1.8-1.3 0-2.5-1.1-2.5-1.1-.1-1.2.4-2.2.4-2.2-.9-.4-1.9-1.4-1.9-1.4.6-1.3 1-1.7 1-1.7-1.5-1.1-1.5-1.8-1.5-1.8.4-1 1.7-1.9 1.7-1.9-.6-.8-1.1-2.3-1.1-2.3 1.1-1.1 2.1-1.4 2.1-1.4-.2-.6-.1-1.2-.1-1.8 0 0-8.7-4.5-9.6-7.5 0 0-.4 2.6-.2 4.3.1 1.5 2.5 3.9 8 7.7-3.4-.5-8.1-2.4-9.2-4.2 0 0 0 2.7.6 4.2.5 1.3 2.9 2.2 8.4 4.9-2.7 1.5-7.5-.2-8.9-1.5 0 0 .8 2.3 1.7 3.8.6.9 2.8 2.4 8.1 1.6-2 2.4-5.7 4.3-8.3 3.1 0 0 .3 2.3 1.8 3 1.1.5 3.6.8 7.4-2.2-2.3 5.7-8 4-8 4s1.3 2.3 2.8 3.1c1.5.6 4.2 0 8.6-4.8zm7.1 4.8c-.4-1.3-1.8-3.3-1.9-3.4 0 .1-.1.4-.8 1.5-2 3.2-3.8 3-3.8 3 1.7.9 4.2-.3 4.2-.3s-.3.8-.4 1c-.7 1.5.3 3.6.3 3.6-.6-2.8 2.4-5.4 2.4-5.4zm-2-3.4s.1 0 0 0c.1 0 0 0 0 0z"></path><path class="st4" d="M196.1 133.4c-.2-.9-.9-.7-1.4-.4-.4.2-.8 0-.8 0-.3-.2-.4-.5.1-.8 2.3-1.1 2.8-2.4 2.8-2.4-1.1.1-2-.2-2-.2s-2.1 2.8-3.7 2c-.5-.2-.7-1.1-.7-1.5 0-.8-.9-1.3-1.4-.7s.1 1.1.6 1.3c.3.1.7.5.6.8-.2.3-.4.2-.7.2s-1.7-.5-2 .5c-.4 1.2 1 1.7 1.7 1 .8-.7 2.1-.7 2.5-.2.1.2.3.8-.8 1.6-.4.3-2.3 1.5-.9 2.7.5.4 1.7.3 2-1.5.2-1.3.6-1.9 1.1-2.2.2-.1 1-.3 1.4 0 .1.1.4.3.4.3.5.8 1.4.2 1.2-.5zm-8-4c.1-.4.5-.6.5-.6-1.7-.6-1.9.9-1.9.9.5-.9 1.4-.3 1.4-.3zm-1.6 3.3c-1.7 1.3-.2 2.8-.2 2.8-.7-1.3.3-1.7.3-1.7-.2-.7-.1-1.1-.1-1.1zm2.7 5.5c-.6-.5-.5-.9-.5-.9-1.1 1.8.8 2.6.8 2.6-1.1-1-.3-1.7-.3-1.7zm7.6-4.8l-.1-.1s.2.4-.1.7c0 0 .1 0 .2.1.3.1.5.4.4 1.1 0 .1 1-1-.4-1.8zm16.4 0c-1.4.8-.4 1.9-.4 1.9-.1-.7.1-1 .4-1.1.1 0 .2-.1.2-.1-.2-.3-.1-.7-.2-.7.1-.1 0-.1 0 0zm-1.5 2c-1.8-.8-1.7-1.3-1.7-1.3s-2 .6-3.2-.1c0 0 .3.9.9 1.8 3 4 5 2 5 2 2.4 1.1.8 5.8.8 5.8 3.7-4.2.9-7.1-1.8-8.2zm3.5-26.7c.6 4.2-1.8 4.6-1.8 4.6s.1 1 .2 2.1c0 1.3-.1 1.4-.1 2 .1 1.2.3 1.3 1.4 1.8 0 0 .4-.4.7-.8.7-1.3-.5-3.3-.5-3.3 1.3 1.6 3.1 1 3.1 1-.1-1.3-1.9-2.5-1.9-2.5 1.6.3 2.9-.6 2.9-.6-.5-.9-2.2-2-2.2-2 1.7-.1 2.8-1.2 2.8-1.2-.5-.7-2.4-1.6-2.4-1.6.9-.5 1.8-2.1 1.8-2.1-1.3-.7-2.8-.5-2.8-.5 2.4-1.7-.2-6.5-.2-6.5.4 7.1-5.1 5.3-4.7 8.9.4 2.9 3.7.7 3.7.7z"></path><path class="st4" d="M228.5 114c.9-1.4 1.7-3.8 1.7-3.8-1.4 1.4-6.2 3-8.9 1.5 5.5-2.7 7.9-3.6 8.4-4.9.6-1.6.6-4.2.6-4.2-1 1.8-5.7 3.7-9.2 4.2 5.6-3.7 7.9-6.2 8-7.7.2-1.7-.2-4.3-.2-4.3-1 2.9-9.6 7.5-9.6 7.5 0 .6.1 1.2-.1 1.8 0 0 1 .3 2.1 1.4 0 0-.5 1.5-1.1 2.3 0 0 1.3 1 1.7 1.9 0 0-.1.7-1.5 1.8 0 0 .4.4 1 1.7 0 0-.9.9-1.9 1.4 0 0 .5 1 .4 2.2 0 0-1.2 1.1-2.5 1.1 0 0-.1.8-.9 1.8-.3.4-1.4 1.3-1.4 1.3s-1.9-.7-2.4-1.3l-.1.3s-.1.6-.8 1.6c0 0 1.4 5.7 8.9 5.9-4.3-1.4-4.6-5.7-4.6-5.7 4.4 4.8 7.1 5.4 8.5 4.7 1.5-.8 2.8-3.1 2.8-3.1s-5.7 1.8-8-4c3.8 3 6.3 2.7 7.4 2.2 1.5-.7 1.8-3 1.8-3-2.5 1.2-6.3-.7-8.3-3.1 5.3.9 7.6-.6 8.2-1.5zm-17.6 9.3s.1 0 0 0c.1 0 0 0 0 0zm4.7 4.5s-1.8.2-3.8-3c-.7-1.2-.8-1.5-.8-1.5-.1.2-1.5 2.1-1.9 3.4 0 0 2.9 2.5 2.4 5.3 0 0 1-2 .3-3.6-.1-.1-.4-1-.4-1s2.5 1.3 4.2.4z"></path><path class="st4" d="M220.7 131.8c-.2 0-.5.1-.7-.2-.2-.3.3-.7.6-.8.5-.2 1-.8.6-1.3-.5-.6-1.4-.2-1.4.7 0 .4-.2 1.2-.7 1.5-1.6.7-3.7-2-3.7-2s-.9.3-2 .2c0 0 .5 1.3 2.8 2.4.5.3.4.6.1.8 0 0-.5.1-.8 0-.5-.2-1.2-.4-1.4.4s.7 1.3 1.4.8c0 0 .3-.2.4-.3.4-.3 1.2-.1 1.4 0 .5.2.9.9 1.1 2.2.3 1.7 1.6 1.9 2 1.5 1.3-1.3-.6-2.5-.9-2.7-1.1-.9-1-1.4-.8-1.6.3-.5 1.6-.5 2.5.2.8.7 2.1.2 1.7-1-.5-1.2-1.8-.7-2.2-.8zm.8-3s.4.2.5.6c0 0 .8-.6 1.4.3 0 0-.1-1.5-1.9-.9zm2 3.9s.2.4-.2 1c0 0 1 .4.3 1.7.1 0 1.6-1.4-.1-2.7zm-2.6 5.5s.8.7-.3 1.7c0 0 1.9-.8.8-2.6 0 0 .1.4-.5.9zm-8.8 1.8c-4.4.5-6.3-4.1-6.3-4.1-.3.3-.5.3-.7.4-.2-.1-.5-.2-.7-.4 0 0-1.9 4.6-6.3 4.1 0 0 .3 1 2 1.1 0 0-3 1.4-1.3 2.8 1.1.9 2-1.6 2-1.6s.1 2.3 2.1 2.4c0 0-3-1.8.1-5.9-.3 2.9.7 5.6 2.1 5.6 1.4 0 2.4-2.7 2.1-5.6 3.1 4.1.1 5.9.1 5.9 2 0 2.1-2.4 2.1-2.4s.9 2.5 2 1.6c1.7-1.4-1.3-2.8-1.3-2.8 1.7-.2 2-1.1 2-1.1zm-12.9-38.4c.3 0 4.3-.1 4.8-.1-.1.3 0 1.1-.9 1.2h-3.3s-.1.8 1.2.5c.3-.1 1.1-.3 1.4.2.2.3.8 1.4-1.2 1.6 0 0 2.9.2 3.1-2.3 0 0 .2 1.8.8 1.9.6 0 .6-1.9.6-1.9 1 2.6 3.5 2.8 3.5 2.8-2.1-1.4-2-5.3-1.9-5.6.1-1.9 1.8-1.7 1.9-2.9.2-1.6-1.7-1.2-1.7-1.2s.8 0 1 .4c.3.9-1.2 1-1.2 1-1.9.5-2.5-.6-3.2-.8-.7-.1-.8.3-1 .5-.1.2-3.1.3-3.7 1-.7.7-.6 1.6-.1 2.1 0 0 .3-1 1.4-1.1 1.1 0 2.9 1.4 3.3 2.2-.5 0-4.6.3-5.2-.1-.3-.3-.7-.8-.7-1.1 0 0-.2 1.1.3 1.4.4.4.5.3.8.3zm4.5-2.5c-.3 0-.5-.2-.5-.5 0-.1 0-.2.1-.2l-1.3.1 2.3-.9h.1v.1l.1.5v.1h-.5c.1.1.1.2.1.3.1.2-.1.5-.4.5zm5.1 7.9c-.7-.1-2.2-.4-2.7-1 0 0-.3.5-1.1.7-.7-.2-1-.7-1-.7-.6.6-1.9 1-2.7 1.1-1.7 4.5-5.5 7.3-2 13.5 3.6 6.4 6.2 7.3 1.2 11.7 0 0 3.2.9 4-1.9 0 0-.1 3 .6 3.8.8-.8.6-3.9.6-3.9.7 2.8 4 1.9 4 1.9-5-4.4-2.4-5.3 1.2-11.7 3.4-6.2-.4-9-2.1-13.5zm1 9.3c0 .1-.1.2-.2.4-.5.8-1.4.9-2.1.6-.4-.1-.5-.2-.6-.3l-.2-.2v2.1l.2-.2.3.4c.1.1.2.3.3.6.2.6.1 1.5-.6 2.1-.1.1-.2.1-.4.2-.1.4-.4.9-1.2 1.3l-.2.1-.2-.1c-.8-.4-1.1-.9-1.2-1.3-.1 0-.2-.1-.4-.2-.8-.5-.9-1.4-.6-2.1.1-.4.2-.5.3-.6l.3-.4.2.2v-2.1l-.2.2c-.1.1-.3.2-.6.3-.6.2-1.5.1-2.1-.6-.1-.1-.1-.2-.2-.4-.4-.1-.9-.4-1.3-1.2l-.1-.2.1-.2c.4-.8.9-1.1 1.3-1.2 0-.1.1-.2.2-.4.5-.8 1.4-.9 2.1-.6.2.1.4.2.5.2l-.2-.2c-.1-.1-.2-.3-.3-.6-.2-.6-.1-1.5.6-2.1.1-.1.2-.1.4-.2.1-.4.4-.9 1.2-1.3l.2-.1.2.1c.8.4 1.1.9 1.2 1.3.1 0 .2.1.4.2.8.5.9 1.4.6 2.1-.1.4-.2.5-.3.6l-.1.2c.1-.1.2-.1.5-.2.6-.2 1.5-.1 2.1.6.1.1.1.2.2.4.4.1.9.4 1.3 1.2l.1.2-.1.2c-.5.8-1 1.1-1.4 1.2z"></path><path class="st4" d="M208.7 114.3c.1-.2.1-.4-.1-.7-.3-.4-.7-.3-.8-.3h-.1l.1.1s.1.1.1.2 0 .3-.3.5c-.1.1-.5.1-.6.1h-1.5V112c0-.1 0-.5.1-.6.2-.2.4-.3.5-.3s.2.1.2.1l.1.1v-.1c.1-.2.1-.6-.3-.8-.3-.2-.5-.1-.7-.1.2-.6-.5-1.1-.5-1.1s-.6.5-.5 1.1c-.2-.1-.4-.1-.7.1-.4.3-.3.7-.3.8v.1l.1-.1s.1-.1.2-.1.3 0 .5.3c.1.1.1.4.1.6v2.2h-1.6c-.1 0-.5 0-.6-.1-.2-.2-.3-.4-.2-.5 0-.1.1-.2.1-.2l.1-.1h-.1c-.2-.1-.6-.1-.8.3-.2.3-.1.5-.1.7-.6-.2-1.1.5-1.1.5s.5.6 1.1.5c-.1.2-.1.4.1.7.3.4.7.3.8.3h.1l-.1-.1s-.1-.1-.1-.2 0-.3.2-.5c.1-.1.4-.1.6-.1h1.6v4c0 .1 0 .4-.1.6-.2.2-.4.3-.5.3s-.2-.1-.2-.1l-.1-.1v.1c-.1.2-.1.6.3.8.3.2.5.1.7.1-.2.6.5 1.1.5 1.1s.6-.5.5-1.1c.2.1.4.1.7-.1.4-.3.3-.7.3-.8v-.1l-.1.1s-.1.1-.2.1-.3 0-.5-.3c-.1-.1-.1-.5-.1-.6v-4h1.5c.1 0 .4 0 .6.1.2.2.3.4.3.5s-.1.2-.1.2l-.1.1h.1c.2.1.6.1.8-.3.2-.3.1-.5.1-.7.6.2 1.1-.5 1.1-.5s-.4-.6-1.1-.5z"></path></g>' + ('<path id="shieldheader" style="' + e.shieldheader + '" class="st5" d="M176.5 77v16.1h56.4V77h-56.4zm12.1 10.9l-2.5-.2s-.2.8-.2 1.8c0 .7.4.9.6 1h-1.7c.2-.1.6-.3.6-1 .1-1-.2-1.8-.2-1.8l-2.5.2.5-.8-2.6-2.4.7-.2-.4-1.7 1.6.3.3-.8 1.1 1.3-.3-3 .9.8 1.1-2.1 1.1 2.1.9-.8-.3 3 1.1-1.3.3.8 1.6-.3-.4 1.7.7.2-2.6 2.4.6.8zm26.1 2.9h-8.1s-.6-1.3-1.8-1.3-1.8 1.3-1.8 1.3h-8v-9.3h1.6v-1.4h1.2s1.8.1 2.7-.3c.9-.4 3.3-1.2 4.4.4 1.1-1.6 3.4-.8 4.4-.4.9.4 2.7.3 2.7.3h1.2v1.4h1.6l-.1 9.3zm11.8-2.9l-2.5-.2s-.3.8-.2 1.8c0 .7.4.9.6 1h-1.7c.2-.1.6-.3.6-1 0-1-.2-1.8-.2-1.8l-2.5.2.5-.8-2.6-2.4.7-.2-.4-1.7 1.6.3.3-.8 1.1 1.3-.3-3 .9.8 1.1-2.1 1.1 2.1.9-.8-.3 3 1.1-1.3.3.8 1.6-.3-.4 1.7.7.2-2.6 2.4.6.8z"></path>') + ('<path id="bookbg" style="' + e.bookbg + '"class="st6" d="M213.8 81.5h-.7v7.9h-3c-1-.1-4.1-2-5.2-.8-1.1-1.2-4.2.7-5.2.8-.5.1-3 0-3 0v-7.9H195v9.3h8.1s.6-1.3 1.8-1.3 1.8 1.3 1.8 1.3h8.1v-9.3h-1z"></path>') + ('<g id="bookoutline" style="' + e.bookoutline + '">') + '<path class="st7" d="M200.8 80.5c-1.1.4-2.9.4-3 .3h-.4v7.8h2.1c.2 0 .7-.2 1.1-.4 1.1-.4 2.5-.9 3.6-.8v-6.6c0-.1-.1-.1-.1-.1-.6-1-2.1-.6-3.3-.2zm4.6 6.9c1.1-.2 2.5.3 3.6.8h.1c.4.2.9.4 1.1.4h2.1v-7.7h-.4c-.2 0-2 .1-3-.3-1.2-.5-2.7-.8-3.4.1l-.1.1v6.6z"></path><path class="st8" d="M211.9 80.1s-1.8.1-2.7-.3c-.8-.3-2.6-.9-3.8-.2v1.2l.1-.1c.7-1 2.2-.6 3.4-.1 1 .4 2.8.4 3 .3h.4v7.7h-2.1c-.2 0-.7-.2-1.1-.4h-.1c-1.1-.4-2.4-.9-3.6-.8v.9c1.4-.4 3.8 1 4.7 1.1.5.1 3 0 3 0v-9.3h-1.2zm-11.3 8.1c-.4.2-.9.4-1.1.4h-2.1v-7.7h.4c.1 0 1.9.1 3-.3 1.2-.5 2.7-.8 3.4.1 0 0 0 .1.1.1v-1.2c-1.2-.8-3-.2-3.8.2-.9.4-2.7.3-2.7.3h-1.2v9.3h3c.9-.1 3.3-1.5 4.6-1.1v-.8c-1.1-.3-2.5.3-3.6.7z"></path></g>' + ('<path id="bookspine" style="' + e.bookspine + '" class="st9" d="M205.4 81.5v-1.9c-.2.1-.4.3-.6.6-.2-.3-.4-.4-.6-.6v8.6l.6.3c.2-.2.4-.3.6-.3v-6.7z"></path>') + ('<path id="books" style="' + e.books + '" class="books" d="M200.8 80.5c-1.1.4-2.9.4-3 .3h-.4v7.8h2.1c.2 0 .7-.2 1.1-.4 1.1-.4 2.5-.9 3.6-.8v-6.6c0-.1-.1-.1-.1-.1-.6-1-2.1-.6-3.3-.2zm11.1.4c-.2 0-2 .1-3-.3-1.2-.5-2.7-.8-3.4.1l-.1.1v6.6c1.1-.2 2.5.3 3.6.8h.1c.4.2.9.4 1.1.4h2.1v-7.7h-.4z"></path>') + ('<g id="leaves" style="' + e.leaves + '">') + '<path class="st11" d="M189.9 84.5l.4-1.7-1.6.3-.3-.8-1.1 1.3.3-3-.9.8-1.1-2.1-1.1 2.1-.9-.8.3 3-1.1-1.3-.3.8-1.6-.3.4 1.7-.7.2 2.6 2.4-.5.8 2.5-.2s.3.8.2 1.8c0 .7-.4.9-.6 1h1.7c-.2-.1-.6-.3-.6-1 0-1 .2-1.8.2-1.8l2.5.2-.5-.8 2.6-2.4-.8-.2zm36.6 3.4l-.5-.8 2.6-2.4-.7-.2.4-1.7-1.6.3-.3-.8-1.1 1.3.3-3-.9.8-1.1-2.1-1.1 2.1-.9-.8.3 3-1.1-1.3-.3.8-1.6-.3.4 1.7-.7.2 2.6 2.4-.5.8 2.5-.2s.2.8.2 1.8c0 .7-.4.9-.6 1h1.7c-.2-.1-.6-.3-.6-1-.1-1 .2-1.8.2-1.8l2.4.2z"></path></g>' + ('<path id="divider" style="' + e.divider + '" class="st12" d="M278 0v149"></path>') + ('<g id="brighterworld" style="' + e.brighterworld + '">') + '<path class="st0" d="M321 58.5V24h12.8c5.5 0 10 1.6 10 8.9 0 4-2 6.8-5.9 7.6v.1c5.1.7 6.5 4 6.5 8.8 0 8.8-7.6 9.1-10.7 9.1H321zm7.2-20.4h4.8c1.6 0 3.8-1.1 3.8-4.4 0-2.5-1.7-4.4-4.2-4.4h-4.5v8.8zm0 15.1h4c1.5 0 5 0 5-4.9 0-3.1-1.1-4.9-4.8-4.9h-4.2v9.8zM358.2 58.5H351V24h13.4c4.9 0 8.1 3.2 8.1 9 0 4.4-1.7 7.7-6.4 8.5v.1c1.6.2 6.3.6 6.3 6.8 0 2.2.1 8.7.8 10.1H366c-1-2.1-.8-4.5-.8-6.7 0-4.1.4-7.6-5.2-7.6h-1.9v14.3zm0-19.6h3.2c2.9 0 3.7-2.9 3.7-5.1 0-3.3-1.4-4.5-3.7-4.5h-3.2v9.6zM379 58.5V24h7.2v34.5H379zM409.1 34.6c0-3.2-.5-6-4.3-6-4.5 0-4.5 6.1-4.5 12.8 0 10.8 1.1 12.7 5.2 12.7 1.2 0 2.5-.3 3.6-.7v-7.7h-3.9v-5.3h11.1v17.5c-2 .4-6.9 1.1-9.8 1.1-12.2 0-13.5-5-13.5-18.1 0-8.7.4-17.6 12.2-17.6 7.1 0 11.5 4 11.1 11.2h-7.2zM439 37.8V24h7.2v34.5H439V43.1h-8.3v15.4h-7.2V24h7.2v13.8h8.3zM475 24v5.7h-8v28.8h-7.2V29.7h-8V24H475zM480.3 58.5V24h18.9v5.3h-11.6v8.5h10.7v5.3h-10.7v10.1h12v5.3h-19.3zM512.7 58.5h-7.2V24h13.4c4.9 0 8.1 3.2 8.1 9 0 4.4-1.7 7.7-6.4 8.5v.1c1.6.2 6.3.6 6.3 6.8 0 2.2.1 8.7.8 10.1h-7.1c-1-2.1-.8-4.5-.8-6.7 0-4.1.4-7.6-5.2-7.6h-1.9v14.3zm0-19.6h3.2c2.9 0 3.7-2.9 3.7-5.1 0-3.3-1.4-4.5-3.7-4.5h-3.2v9.6zM317.9 67.4h7.4l4.5 24.3h.1l5.5-24.3h8.5l5.2 24.3h.1l4.3-24.3h7.1l-7.7 34.5h-8l-5.4-25.3h-.1l-6 25.3h-7.8l-7.7-34.5zM364.5 84.6c0-9.1 0-17.8 11.9-17.8s11.9 8.7 11.9 17.8c0 9 0 17.8-11.9 17.8s-11.9-8.7-11.9-17.8zm16.5 0c0-8.9-.5-12.7-4.6-12.7s-4.6 3.8-4.6 12.7.5 12.7 4.6 12.7 4.6-3.8 4.6-12.7zM402.2 101.9H395V67.4h13.4c4.9 0 8.1 3.2 8.1 9 0 4.4-1.7 7.7-6.4 8.5v.1c1.6.2 6.3.6 6.3 6.8 0 2.2.1 8.7.8 10.1H410c-1-2.1-.8-4.5-.8-6.7 0-4.1.4-7.6-5.2-7.6h-1.9v14.3zm0-19.6h3.2c2.9 0 3.7-2.9 3.7-5.1 0-3.3-1.4-4.5-3.7-4.5h-3.2v9.6zM423.1 101.9V67.4h7.2v28.8h10.8v5.7h-18zM446.5 67.4h12.1c9.5 0 11.2 6.3 11.2 17.1 0 5.3.8 17.5-11.5 17.5h-11.8V67.4zm7.2 29.2h3.5c4.4 0 5.3-3.3 5.3-12 0-6.4 0-12-5-12h-3.7v24z"></path></g></svg>'),
                this.SVGLogo);
            },
        }, {
            key: "condensed",
            value: function() {
                var c = document.querySelector("#mcmaster-header");
                c.className = "condensed";
            },
        }, {
            key: "getFooter",
            value: function() {
                return this.footer;
                // return (
                //     (this.footer =
                //         '<footer id="mac-footer" class="maroon" style="background:' +
                //         this.footerColor +
                //         '; ">\n        <svg id="radiance" xmlns="https://www.w3.org/2000/svg" viewBox="0 0 214.1 55.7"><style>#radiance .st0{fill:#A45853;}</style><path class="st0" d="M0 24.4c.1-.2.3-.4.6-.4.2 0 .4.1.3.3-.1.2-.4.4-.6.4-.1 0-.2 0-.2-.1M10.4 0c0 .1 0 .2-.1.2-.2.3-.8.6-1.2.5-.4 0-.6-.3-.3-.6l.1-.1m6 0c.2.1.2.3 0 .6-.3.3-.8.6-1.3.5-.5 0-.6-.3-.4-.7.3-.2.6-.3.8-.4m27.1 0c-.3.2-.7.3-1 .3-.3 0-.4-.1-.5-.3m5.6 0c-.3.3-.9.5-1.3.5s-.6-.2-.5-.5m5.7 0v.1c-.3.4-.9.7-1.5.6-.5 0-.7-.4-.5-.7m5.8 0c0 .1 0 .2-.1.3-.3.4-1 .7-1.5.7s-.7-.4-.5-.8L51 0m5.4 0c0 .1 0 .3-.1.4-.3.4-.9.7-1.4.7-.5 0-.8-.4-.5-.8l.4-.4m5.1.1c.1.1.1.3 0 .5-.3.4-.9.7-1.4.7-.5 0-.8-.4-.5-.7.1-.2.4-.4.6-.5m4.8 0c.2.1.3.3.1.6-.3.4-.9.7-1.4.7-.5 0-.8-.3-.5-.7.2-.3.5-.5.9-.6m4.4 0c.2.1.3.4.1.6-.2.4-.9.7-1.4.7-.5 0-.8-.3-.5-.7.2-.3.5-.5.9-.6m4.5 0c.2.1.3.3.1.6-.2.4-.9.7-1.4.8-.5 0-.8-.3-.5-.7.2-.3.5-.5.9-.6m4.5-.1c.1.1.1.3 0 .5-.2.4-.8.8-1.4.8-.5 0-.8-.3-.5-.7.1-.2.4-.4.7-.6m4.8 0c0 .1 0 .2-.1.4-.2.4-.8.8-1.4.8-.5 0-.8-.3-.5-.7.1-.2.3-.4.5-.5m5.1 0v.1c-.3.5-.9.8-1.4.9-.5 0-.8-.3-.6-.7 0-.1.1-.2.2-.3m5.2 0c-.3.4-.8.7-1.2.7-.5 0-.8-.3-.6-.7M88 0c-.3.2-.6.3-.9.4-.4 0-.6-.1-.7-.4m16 0v.3c-.2.5-.8 1.1-1.4 1.2-.6.1-.9-.2-.7-.8.1-.2.3-.5.5-.7m5.2 0c-.3.3-.7.6-1 .6-.6.1-.9-.2-.8-.6m13.9 0s0 .1 0 0c-.1.7-.7 1.3-1.4 1.5-.6.2-1-.2-.9-.8.1-.2.2-.5.4-.7m5.4 0c-.1.1-.2.1-.3.2-.4.1-.6 0-.8-.2m11 0v.2c-.1.6-.7 1.3-1.3 1.5-.6.2-1.1-.1-1-.7.1-.3.3-.7.6-1m17.6 0c-.2.5-.6 1-1.1 1.2-.6.2-1.1-.1-1-.7 0-.2.1-.3.2-.5m37 0c-.1.1-.2.2-.4.2-.4.2-.7.1-.9-.2m21.5 0c-.1.3-.3.6-.7.8-.4.2-.7 0-.7-.3 0-.1.1-.3.2-.4m-49.3 2.7c.6-.2 1.1.1 1 .7 0 .6-.6 1.2-1.2 1.4-.6.2-1.1-.1-1-.7.1-.5.6-1.2 1.2-1.4zm-6.3 2.1c.6-.2 1 .1 1 .7-.1.6-.6 1.2-1.2 1.4-.6.2-1-.1-1-.7.1-.6.6-1.2 1.2-1.4zm-.7 6c.6-.2 1 .2.9.7-.1.6-.6 1.1-1.2 1.3-.6.1-1-.2-.9-.7.2-.6.7-1.1 1.2-1.3zm-4.6-9.8c.6-.2 1.1.1 1 .7-.1.6-.6 1.3-1.3 1.5-.6.2-1.1-.1-1-.7.2-.6.7-1.3 1.3-1.5zm-.6 5.6c.6-.2 1 .1 1 .7-.1.6-.6 1.2-1.2 1.4-.6.2-1-.2-1-.8 0-.5.6-1.1 1.2-1.3zm-4.9-3.8c.6-.2 1.1.1 1 .7-.1.6-.7 1.3-1.3 1.5-.6.2-1.1-.2-1-.8.1-.6.7-1.2 1.3-1.4zm-.8 5.3c.6-.2 1 .2.9.8-.1.6-.7 1.2-1.3 1.3-.6.1-1-.2-.9-.8.2-.5.7-1.1 1.3-1.3zm-1.7 10.9c.5-.1.9.3.8.8-.1.5-.6 1-1.2 1.1-.5.1-.9-.3-.8-.8.1-.6.6-1 1.2-1.1zm-2.8-14.6c.6-.2 1.1.2 1 .8-.1.6-.7 1.3-1.3 1.4-.6.2-1-.2-.9-.8 0-.6.6-1.2 1.2-1.4zm-.8 5c.6-.1 1 .2.9.8-.1.6-.7 1.2-1.3 1.3-.6.1-1-.2-.9-.8.1-.5.7-1.1 1.3-1.3zm-.9 5.2c.6-.1 1 .2.9.8-.1.6-.7 1.1-1.2 1.2-.6.1-1-.3-.8-.8 0-.6.5-1.1 1.1-1.2zm-.2 6c-.1.5-.6 1-1.2 1.1-.5.1-.9-.3-.8-.8.1-.5.6-1 1.2-1.1.6-.1.9.2.8.8zm-2.3-19.6c.6-.2 1.1.1 1 .7-.1.6-.7 1.3-1.3 1.4-.6.2-1.1-.2-.9-.8 0-.5.6-1.1 1.2-1.3zm-.8 4.7c.6-.2 1 .2.9.8-.1.6-.7 1.2-1.3 1.4-.6.1-1-.2-.9-.8.1-.6.7-1.2 1.3-1.4zm-.9 4.9c.6-.1 1 .2.9.8-.1.6-.7 1.2-1.3 1.3-.6.1-1-.3-.9-.8.1-.6.7-1.2 1.3-1.3zm-1 4.9c.6-.1 1 .3.9.8-.1.6-.7 1.1-1.3 1.2-.6.1-.9-.3-.8-.8.1-.6.7-1.1 1.2-1.2zm-.2 5.7c-.1.5-.7 1-1.2 1.1-.5.1-.9-.3-.8-.8.1-.5.6-1 1.2-1.1.6-.1.9.3.8.8zm-1.8-18.9c.6-.2 1 .2.9.8-.1.6-.7 1.2-1.4 1.4-.6.2-1-.2-.9-.8.1-.6.7-1.2 1.4-1.4zm-1 4.6c.6-.1 1 .2.9.8-.1.6-.7 1.2-1.3 1.3-.6.1-1-.3-.9-.8.1-.6.7-1.2 1.3-1.3zm-2.2 5.8c.1-.6.7-1.1 1.3-1.2.6-.1 1 .3.9.8-.1.6-.7 1.1-1.3 1.2-.6.2-1-.2-.9-.8zm.3 3.5c.6-.1 1 .3.8.9-.1.6-.7 1.1-1.3 1.2-.6.1-.9-.3-.8-.9.2-.6.7-1.1 1.3-1.2zm-.3 5.6c-.1.5-.7 1-1.2 1s-.9-.3-.8-.9c.1-.5.7-1 1.2-1 .6 0 .9.4.8.9zm-2.8-17c.1-.6.7-1.2 1.4-1.3.6-.2 1 .2.9.8-.1.6-.7 1.2-1.4 1.3-.6.1-1-.2-.9-.8zm-1 4.3c.1-.6.7-1.1 1.3-1.3.6-.1 1 .2.9.8-.1.6-.7 1.2-1.4 1.3-.5.2-.9-.2-.8-.8zM94 24.2c-.5 0-.8-.4-.7-.9.2-.5.7-.9 1.2-.9s.9.4.7.9c-.1.4-.6.9-1.2.9zm1.1 10.2c.4 0 .7.4.6.7-.1.4-.6.7-1 .7s-.7-.4-.6-.7c.1-.4.6-.7 1-.7zM20 18.9c.2-.4.7-.7 1.2-.7s.7.3.5.7c-.2.4-.7.7-1.2.7-.4 0-.7-.3-.5-.7zm-.2-6.7c-.5 0-.7-.3-.5-.7.2-.4.8-.7 1.3-.7s.7.3.5.7c-.2.4-.8.7-1.3.7zm2 2.9c.2-.4.8-.7 1.3-.7s.7.3.5.7c-.2.4-.8.7-1.2.7-.6.1-.8-.2-.6-.7zm-.6 11.4c.1-.4.6-.7 1-.7s.6.3.5.6c-.1.4-.6.7-1 .7s-.7-.2-.5-.6zm1.5-3.9c.2-.4.7-.7 1.1-.7.5 0 .7.3.5.7-.2.4-.7.7-1.1.8-.4-.1-.7-.4-.5-.8zm1.6-3.8c.2-.4.7-.8 1.2-.8s.7.3.5.7c-.2.4-.7.8-1.2.8-.4.1-.6-.3-.5-.7zm73.8-8.3c.6-.1.9.3.8.9-.2.6-.8 1.1-1.4 1.1-.6.1-.9-.4-.8-.9.2-.5.8-1 1.4-1.1zm-.2-2.6c.2-.5.8-1 1.4-1.1.6-.1.9.3.8.8-.2.6-.8 1.1-1.4 1.1-.6.1-1-.3-.8-.8zm-1 6.5c.6 0 .9.4.8.9-.2.6-.8 1-1.3 1.1-.6 0-.9-.4-.7-.9.1-.6.7-1.1 1.2-1.1zM96 8.1c-.2.5-.8 1-1.4 1.1-.6.1-.9-.3-.7-.9.2-.5.8-1 1.4-1.1.6 0 .9.4.7.9zm-1.9 2.8c.6-.1.9.3.7.9-.2.6-.8 1-1.4 1.1-.6 0-.9-.4-.7-.9.2-.6.8-1 1.4-1.1zm-1.2 3.8c.6 0 .9.4.7.9-.2.5-.8 1-1.3 1-.6 0-.9-.4-.7-.9.1-.5.7-1 1.3-1zm-.5 4.7c-.2.5-.7 1-1.3 1-.6 0-.9-.4-.7-.9.2-.5.7-1 1.3-1 .5 0 .9.4.7.9zm-.3-10.9c-.2.5-.8 1-1.4 1.1-.6 0-.9-.3-.7-.9.2-.5.8-1 1.4-1 .6-.1.9.3.7.8zm-2 2.7c.6 0 .9.4.7.9-.2.5-.8 1-1.4 1-.6 0-.9-.4-.7-.9.3-.5.9-.9 1.4-1zm-1.2 3.7c.6 0 .9.4.7.9-.2.5-.8 1-1.3 1-.6 0-.9-.4-.7-.9.1-.5.7-1 1.3-1zm-.5 4.6c-.2.5-.8 1-1.3 1-.6 0-.9-.4-.7-.9.2-.5.8-.9 1.3-1 .5 0 .9.4.7.9zm-.2-10.7c-.2.5-.8 1-1.4 1-.6 0-.9-.4-.7-.9.3-.4.9-.9 1.4-.9.6-.1.9.3.7.8zm-1.9 2.6c.6 0 .9.4.7.9-.2.5-.8 1-1.4 1-.6 0-.9-.4-.7-.9.2-.5.8-.9 1.4-1zM85 15c.6 0 .9.4.7.9-.2.5-.8 1-1.4 1-.6 0-.9-.4-.7-.9.2-.5.8-1 1.4-1zm-.6 4.6c-.2.5-.8.9-1.3.9s-.8-.4-.7-.9c.2-.5.7-.9 1.3-.9.6 0 .9.4.7.9zm0-10.5c-.2.5-.8.9-1.4 1-.6 0-.9-.4-.7-.9.2-.5.8-.9 1.4-1 .6 0 .9.4.7.9zm-2 2.5c.6 0 .9.4.7.9-.2.5-.8 1-1.4 1-.6 0-.9-.4-.7-.9.3-.5.9-1 1.4-1zm-1.2 3.5c.6 0 .9.4.7.9-.2.5-.8.9-1.3 1-.6 0-.9-.4-.7-.9.1-.5.7-1 1.3-1zm-1.3 3.6c.5 0 .8.4.7.9-.2.5-.8.9-1.3.9s-.8-.4-.7-.9c.2-.5.7-.9 1.3-.9zm-.6 4.5c-.2.5-.7.9-1.2.9s-.8-.4-.6-.9c.2-.5.7-.9 1.2-.9.4.1.7.5.6.9zm0-10.6c-.2.5-.8.9-1.4.9-.6 0-.8-.4-.7-.9.2-.5.8-.9 1.4-.9.6 0 .9.4.7.9zm-1.9 2.6c.6 0 .8.4.7.9-.2.5-.8.9-1.3.9-.6 0-.9-.4-.7-.9.1-.5.7-.9 1.3-.9zm-1.3 3.5c.5 0 .8.4.6.9-.2.5-.8.9-1.3.9s-.8-.4-.6-.9c.2-.5.7-.9 1.3-.9zm-.7 4.5c-.2.5-.7.9-1.3.9-.5 0-.8-.4-.6-.9.2-.5.7-.9 1.3-.9.5 0 .8.4.6.9zm.2-10.5c-.2.5-.8.9-1.4.9-.6 0-.8-.4-.6-.9.2-.5.8-.9 1.4-.9.5 0 .8.4.6.9zm-2 2.5c.5 0 .8.4.6.9-.2.5-.8.9-1.3.9-.6 0-.8-.4-.6-.9.1-.5.8-.9 1.3-.9zm-2 5.2c-.5 0-.8-.4-.6-.9.2-.5.8-.9 1.3-.9s.8.4.6.9c-.2.6-.8 1-1.3.9zm0 2.7c-.2.5-.7.9-1.2.8-.5 0-.8-.4-.6-.9.2-.5.7-.9 1.2-.8.5 0 .8.4.6.9zm1.7-13.7c-.2.5-.8.9-1.4.9-.5 0-.8-.4-.6-.9.2-.5.8-.9 1.4-.9.5.1.8.5.6.9zm-2.1 2.4c.5 0 .8.4.6.9-.2.5-.8.9-1.4.9-.5 0-.8-.4-.6-.9.3-.5.9-.9 1.4-.9zm-1.3 3.4c.5 0 .8.4.6.9-.2.5-.8.9-1.3.9s-.8-.4-.6-.9c.1-.5.7-.9 1.3-.9zm-2.1 5.2c-.5 0-.8-.4-.6-.9.2-.5.8-.9 1.3-.9s.8.4.6.9c-.2.5-.7.9-1.3.9zm0 2.6c-.2.5-.7.9-1.2.8-.5 0-.8-.4-.6-.9.2-.5.7-.8 1.2-.8s.8.4.6.9zm1.8-13.5c-.2.5-.8.9-1.4.9-.5 0-.8-.4-.6-.9.2-.5.9-.9 1.4-.9.5 0 .8.4.6.9zm-2.1 2.3c.5 0 .8.4.6.9-.2.5-.8.9-1.4.9-.5 0-.8-.4-.6-.9.3-.5.9-.9 1.4-.9zm-1.4 3.3c.5 0 .8.4.6.9-.2.5-.8.9-1.3.9s-.8-.4-.6-.9c.2-.5.8-.9 1.3-.9zm-2.6 4.3c.2-.5.8-.9 1.3-.8.5 0 .8.4.6.9-.2.5-.8.9-1.3.9-.6-.1-.8-.5-.6-1zm.5 3.5c-.2.5-.7.8-1.2.8s-.8-.4-.6-.9c.2-.5.7-.8 1.2-.8s.8.4.6.9zm1.9-13.5c-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.9.2-.5.8-.8 1.4-.8.6.1.8.5.6.9zm-1.4 3.2c-.2.5-.8.9-1.4.9-.5 0-.8-.4-.6-.9.2-.5.8-.9 1.4-.8.5 0 .8.4.6.8zm-2.1 2.5c.5 0 .8.4.6.9-.2.5-.8.9-1.3.9s-.8-.4-.6-.9c.2-.6.8-.9 1.3-.9zm-2.7 4.2c.2-.5.8-.8 1.3-.8s.8.4.6.9c-.2.5-.8.9-1.3.8-.5 0-.8-.4-.6-.9zm.5 3.5c-.2.5-.7.8-1.2.8s-.8-.4-.6-.9c.2-.5.7-.8 1.2-.8s.8.4.6.9zm2.1-13.4c-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.9.2-.5.9-.8 1.4-.8.5 0 .8.4.6.9zm-1.5 3.2c-.2.5-.8.9-1.4.8-.5 0-.8-.4-.6-.9.2-.5.8-.8 1.4-.8.5 0 .8.4.6.9zm-1.5 3.3c-.2.5-.8.9-1.3.8-.5 0-.8-.4-.6-.9.2-.5.8-.8 1.3-.8s.8.4.6.9zM56 19.2c.2-.5.8-.8 1.3-.8s.8.4.6.9c-.2.5-.8.8-1.3.8-.6 0-.8-.4-.6-.9zm.4 3.5c-.2.5-.7.8-1.2.8s-.8-.4-.6-.9c.2-.5.7-.8 1.2-.8s.8.4.6.9zm2.2-13.4c-.2.5-.9.8-1.4.8-.5 0-.8-.4-.6-.9.2-.5.9-.8 1.4-.8.6.1.8.4.6.9zM57 12.5c-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.9.2-.5.8-.8 1.4-.8.6 0 .9.4.6.9zm-1.5 3.3c-.2.5-.8.8-1.3.8s-.8-.4-.6-.9c.2-.5.8-.8 1.4-.8.5 0 .7.4.5.9zm-3.3 3.3c.2-.5.8-.8 1.3-.8s.8.4.6.9c-.2.5-.8.8-1.3.8-.5-.1-.8-.5-.6-.9zm.4 3.5c-.2.5-.7.8-1.2.8s-.8-.4-.6-.8c.2-.5.7-.8 1.2-.8.5-.1.8.3.6.8zm2.3-13.4c-.2.5-.9.8-1.4.8-.5 0-.8-.4-.6-.9.2-.5.9-.8 1.4-.8.6.1.8.4.6.9zm-1.6 3.2c-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.9.2-.5.8-.8 1.4-.8.6 0 .8.4.6.9zm-1.6 3.3c-.2.5-.8.8-1.3.8s-.8-.4-.6-.9c.2-.5.8-.8 1.3-.8.6 0 .9.4.6.9zM48.4 19c.2-.5.8-.8 1.3-.8s.8.4.6.9c-.2.5-.8.8-1.3.8-.6-.1-.8-.4-.6-.9zm.4 3.5c-.2.4-.7.8-1.2.8s-.8-.4-.6-.8c.2-.4.7-.8 1.2-.8s.8.3.6.8zm2.4-13.4c-.2.4-.9.8-1.4.8-.5 0-.8-.4-.5-.8.2-.4.9-.8 1.4-.8.4 0 .7.3.5.8zm-1.7 3.1c-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.9.2-.5.8-.8 1.4-.8.6.1.8.5.6.9zm-1.6 3.3c-.2.5-.8.8-1.3.8s-.8-.4-.6-.9c.2-.5.8-.8 1.3-.8.6.1.8.5.6.9zm-1.5 3.4c-.2.5-.8.8-1.3.8s-.8-.4-.6-.8c.2-.5.8-.8 1.3-.8s.8.4.6.8zm1-10c-.2.4-.9.8-1.4.8-.5 0-.8-.4-.5-.8.2-.4.9-.8 1.4-.8.5 0 .7.4.5.8zm-1.7 3.2c-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.9.2-.4.8-.8 1.4-.8.6.1.8.5.6.9zm-1.6 3.3c-.2.5-.8.8-1.3.8s-.8-.4-.6-.8c.2-.5.8-.8 1.3-.8s.8.4.6.8zm-3.5 3.4c.2-.4.8-.8 1.3-.8s.7.4.6.8c-.2.4-.8.8-1.3.8-.5.1-.8-.3-.6-.8zm.3 3.6c-.2.4-.7.8-1.2.8s-.7-.4-.6-.8c.2-.4.7-.8 1.2-.8.6 0 .8.3.6.8zm2.7-13.6c-.2.4-.9.8-1.4.8-.5 0-.8-.4-.5-.8.2-.5.8-.9 1.3-.8.6 0 .8.4.6.8zM41.8 12c-.2.4-.8.8-1.4.8-.5 0-.8-.4-.5-.8.2-.4.8-.8 1.4-.8.5 0 .7.4.5.8zm-1.7 3.3c-.2.4-.8.8-1.3.8s-.8-.4-.6-.8c.2-.4.8-.8 1.3-.8.6 0 .8.4.6.8zm-3.4 3.5c.2-.4.8-.8 1.3-.8s.7.4.5.8c-.2.4-.8.8-1.2.8-.5 0-.8-.4-.6-.8zm.2 3.6c-.2.4-.7.8-1.2.8s-.7-.3-.5-.8c.2-.4.7-.8 1.2-.8s.7.3.5.8zm2.8-13.8c-.2.4-.9.8-1.4.7-.5 0-.8-.4-.5-.8.2-.4.9-.7 1.4-.7.5.1.7.4.5.8zm-1.8 3.3c-.2.4-.8.8-1.3.8s-.8-.4-.5-.8c.2-.4.8-.8 1.4-.8.4 0 .6.3.4.8zm-1.8 3.4c-.2.4-.8.8-1.3.8s-.8-.4-.5-.8c.2-.4.8-.8 1.3-.8s.7.3.5.8zm-1.7 3.5c-.2.4-.7.8-1.2.8s-.7-.4-.5-.8c.2-.4.8-.8 1.2-.8.5 0 .7.3.5.8zm1.3-10.3c-.2.4-.9.7-1.4.7-.5 0-.8-.4-.5-.8.2-.4.9-.7 1.4-.7.5 0 .7.4.5.8zm-1.9 3.3c-.2.4-.8.8-1.3.8s-.8-.4-.5-.8c.2-.4.8-.8 1.4-.7.4-.1.7.2.4.7zM32 15.2c-.2.4-.8.8-1.3.8s-.8-.4-.5-.8c.2-.4.8-.8 1.3-.8s.7.4.5.8zm-1.7 3.6c-.2.4-.7.8-1.2.8s-.7-.3-.5-.8c.2-.4.7-.8 1.2-.8s.7.3.5.8zm-.6-7.1c-.2.4-.8.8-1.3.7-.5 0-.7-.4-.5-.8.2-.4.8-.7 1.3-.7s.7.3.5.8zm-1.9 3.5c-.2.4-.8.8-1.3.8s-.7-.3-.5-.8c.2-.4.8-.8 1.3-.8s.8.3.5.8zm-2.3 11.1c.2-.4.6-.7 1.1-.7.4 0 .6.3.5.7-.2.4-.6.7-1 .7-.5 0-.8-.3-.6-.7zm1.5-3.8c.2-.4.7-.7 1.1-.8.5 0 .7.3.5.7-.2.4-.7.7-1.1.8-.5 0-.7-.3-.5-.7zm1.3 7.4c.1-.4.6-.7 1-.7s.6.3.5.6c-.1.4-.6.7-1 .7s-.6-.2-.5-.6zm1.4-3.8c.2-.4.6-.7 1.1-.7.4 0 .7.3.5.7-.2.4-.6.7-1.1.7-.4 0-.7-.3-.5-.7zm1.4-3.7c.2-.4.7-.8 1.2-.8s.7.3.5.7c-.2.4-.7.8-1.2.8-.4.1-.6-.3-.5-.7zm1.3 7.3c.1-.4.6-.7 1-.7s.6.3.5.7c-.1.4-.6.7-1 .7s-.6-.3-.5-.7zm1.4-3.7c.2-.4.7-.7 1.1-.7.4 0 .7.3.5.7-.2.4-.6.7-1.1.7-.4 0-.7-.3-.5-.7zm1.4 7.3c.1-.4.6-.7.9-.7.4 0 .6.3.5.6-.1.4-.5.7-.9.7s-.6-.3-.5-.6zm1.3-3.7c.1-.4.6-.7 1-.7s.6.3.5.7c-.1.4-.6.7-1 .7s-.7-.3-.5-.7zm1.3-3.6c.2-.4.7-.7 1.1-.7.5 0 .7.3.5.7-.2.4-.7.7-1.1.8-.4-.1-.7-.4-.5-.8zm1.4 7.2c.1-.4.6-.7.9-.7.4 0 .6.3.5.6-.1.4-.6.6-.9.7-.4 0-.6-.3-.5-.6zm1.2-3.6c.1-.4.6-.7 1-.7s.7.3.5.7c-.1.4-.6.7-1 .7s-.6-.4-.5-.7zm1.3-3.6c.2-.4.7-.8 1.1-.8.5 0 .7.3.5.8-.2.4-.7.8-1.1.8-.4-.1-.6-.4-.5-.8zm1.4-3.6c.2-.4.7-.8 1.2-.8s.7.4.6.8c-.2.4-.7.8-1.2.8s-.8-.4-.6-.8zm1.3 7.1c.1-.4.6-.7 1.1-.7.4 0 .7.3.5.7-.1.4-.6.7-1.1.7-.5.1-.7-.3-.5-.7zm1.2-3.5c.2-.4.7-.8 1.1-.8.5 0 .7.4.5.8-.2.4-.7.8-1.1.8-.4 0-.6-.4-.5-.8zm1.4 7.1c.1-.4.6-.7 1-.7s.6.3.5.7c-.1.4-.6.7-1 .7s-.6-.3-.5-.7zm1.2-3.5c.2-.4.6-.7 1.1-.7.4 0 .7.3.5.7-.1.4-.6.7-1.1.7-.4 0-.6-.3-.5-.7zm1.3-3.6c.2-.4.7-.8 1.2-.8s.7.4.6.8c-.2.4-.7.8-1.2.8s-.8-.3-.6-.8zm1.3 7.1c.1-.4.6-.7 1-.7s.6.3.5.7c-.1.4-.6.7-1 .7s-.6-.3-.5-.7zm1.3-3.5c.2-.4.6-.7 1.1-.7.5 0 .7.4.5.8-.2.4-.6.7-1.1.7-.5 0-.7-.4-.5-.8zm1.2-3.5c.2-.4.7-.8 1.2-.8s.7.4.6.8c-.2.4-.7.8-1.2.8s-.7-.3-.6-.8zm1.4 7.1c.1-.4.6-.7 1-.7s.7.3.5.7c-.1.4-.6.7-1 .7s-.7-.3-.5-.7zm1.2-3.5c.1-.4.6-.7 1.1-.7.5 0 .7.4.5.8-.2.4-.6.7-1.1.7-.4 0-.7-.4-.5-.8zm1.2-3.5c.2-.4.7-.8 1.2-.8s.7.4.6.8c-.2.4-.7.8-1.2.8s-.7-.3-.6-.8zm1.4 7.1c.1-.4.6-.7 1-.7s.7.3.5.7c-.1.4-.6.7-1 .7s-.7-.3-.5-.7zm1.2-3.5c.2-.4.6-.7 1.1-.7.5 0 .7.4.6.8-.2.4-.6.7-1.1.7-.5 0-.8-.4-.6-.8zm1.2-3.5c.2-.4.7-.8 1.2-.8s.7.4.6.8c-.2.4-.7.8-1.2.8s-.8-.3-.6-.8zm1.4 7.1c.1-.4.6-.7 1-.7s.7.3.5.7c-.1.4-.6.7-1 .7-.4.1-.6-.3-.5-.7zm1.2-3.4c.2-.4.7-.8 1.1-.7.5 0 .7.4.6.8-.2.4-.6.8-1.1.7-.5-.1-.8-.4-.6-.8zm1.2-3.6c.2-.5.7-.8 1.2-.8s.8.4.6.8c-.2.5-.7.8-1.2.8-.5.1-.8-.3-.6-.8zm1.4 7.2c.1-.4.6-.7 1-.7s.7.4.5.7c-.1.4-.6.7-1 .7s-.6-.3-.5-.7zm1.2-3.5c.2-.4.7-.8 1.1-.7.5 0 .7.4.6.8-.2.4-.6.8-1.1.7-.5 0-.8-.4-.6-.8zm1.2-3.5c.2-.5.7-.8 1.2-.8s.8.4.6.9c-.2.5-.7.8-1.2.8-.5-.1-.8-.5-.6-.9zm1.5 7.2c.1-.4.6-.7 1-.7s.7.4.5.8c-.1.4-.6.7-1 .7-.4-.1-.7-.4-.5-.8zm1.1-3.5c.2-.4.7-.8 1.1-.7.5 0 .7.4.6.8-.1.4-.7.8-1.1.7-.5 0-.7-.4-.6-.8zm1.2-3.6c.2-.5.7-.8 1.2-.8s.8.4.6.9c-.2.5-.7.8-1.2.8s-.7-.4-.6-.9zm1.5 7.3c.1-.4.6-.7 1-.7s.7.4.5.8c-.1.4-.6.7-1 .7-.4-.1-.6-.4-.5-.8zm1.2-3.6c.1-.4.6-.8 1.1-.7.5 0 .7.4.6.8-.1.4-.6.8-1.1.7-.5 0-.7-.3-.6-.8zm1.2-3.6c.2-.5.7-.8 1.2-.8s.8.4.6.9c-.2.5-.7.8-1.2.8s-.8-.4-.6-.9zm1.5 7.4c.1-.4.6-.7 1-.7s.7.4.5.8c-.1.4-.6.7-1 .7-.4-.1-.6-.4-.5-.8zm1.2-3.6c.1-.4.7-.8 1.1-.8.5 0 .7.4.6.8-.1.4-.7.8-1.1.8-.5 0-.7-.4-.6-.8zm1.2-3.7c.2-.5.7-.8 1.2-.8s.8.4.6.9c-.2.5-.7.8-1.2.8s-.8-.4-.6-.9zm1.8-2.7c-.5 0-.8-.4-.7-.9.2-.5.7-.9 1.2-.9s.8.4.7.9c-.1.5-.7.9-1.2.9zm1 6.6c.1-.5.6-.8 1.1-.8.5 0 .7.4.6.8-.1.4-.6.8-1.1.8-.5 0-.8-.4-.6-.8zm1.2-3.8c.2-.5.7-.8 1.2-.8s.8.4.6.9c-.2.5-.7.8-1.2.8s-.8-.4-.6-.9zm1.8-2.8c-.5 0-.8-.4-.7-.9.2-.5.7-.9 1.2-.9s.8.4.7.9c-.1.5-.7.9-1.2.9zm1 6.7c.1-.4.6-.8 1.1-.8.5 0 .8.4.6.8-.1.4-.7.8-1.1.8-.5 0-.7-.4-.6-.8zm1.2-3.8c.1-.5.7-.8 1.2-.8s.8.4.6.9c-.1.5-.7.9-1.2.8-.5 0-.8-.4-.6-.9zm1.8-2.9c-.5 0-.8-.4-.7-.9.2-.5.7-.9 1.3-.9.5 0 .8.4.7.9-.2.5-.7.9-1.3.9zm1.2 6.8c.1-.4.6-.8 1.1-.8.5 0 .8.4.6.8-.1.4-.6.8-1.1.8-.5 0-.8-.3-.6-.8zm1.1-3.8c.1-.5.7-.9 1.2-.9s.8.4.7.9c-.1.5-.7.9-1.2.9-.5-.1-.8-.5-.7-.9zm3-6.9c-.6 0-.9-.4-.7-.9.2-.5.7-1 1.3-1 .6 0 .9.4.7.9-.2.5-.7.9-1.3 1zm1.2 6.9c.1-.5.7-.9 1.2-.9s.8.4.7.9c-.1.5-.7.9-1.2.9-.5-.1-.8-.5-.7-.9zm1.9-3.1c-.5 0-.9-.4-.7-.9.1-.5.7-.9 1.2-1 .5 0 .9.4.7.9-.1.5-.7.9-1.2 1zm1.1-4.1c-.6 0-.9-.4-.7-.9.2-.5.7-1 1.3-1 .6 0 .9.4.8.9-.3.6-.8 1-1.4 1zm1.1-4c-.6 0-.9-.4-.8-.9.2-.5.8-1 1.3-1.1.6-.1.9.3.8.9-.1.6-.7 1.1-1.3 1.1zm.3 11.1c.1-.5.7-.9 1.2-.9s.8.4.7.9c-.1.5-.7.9-1.2.9-.6 0-.9-.4-.7-.9zm1.8-3.2c-.5 0-.9-.4-.7-.9.1-.5.7-.9 1.2-1 .5 0 .9.4.7.9-.1.5-.7 1-1.2 1zm1.1-4.1c-.6 0-.9-.4-.8-.9.1-.5.7-1 1.3-1.1.6-.1.9.4.8.9-.1.5-.7 1-1.3 1.1zm1.1-4.2c-.6.1-.9-.4-.8-.9.2-.6.7-1.1 1.3-1.1.6-.1.9.3.8.9-.1.6-.7 1.1-1.3 1.1zm.5 11.5c.1-.5.6-.9 1.2-.9.5 0 .8.4.7.8-.1.5-.7.9-1.2.9-.6 0-.9-.4-.7-.8zm1.8-3.4c-.5 0-.9-.4-.7-.9.1-.5.7-1 1.2-1s.9.4.7.9c-.1.5-.7.9-1.2 1zm1.1-4.3c-.6 0-.9-.4-.8-.9.1-.5.7-1 1.3-1.1.6-.1.9.3.8.9-.2.5-.8 1-1.3 1.1zm1-4.3c-.6.1-1-.3-.8-.9.1-.6.7-1.1 1.3-1.2.6-.1 1 .3.8.9-.1.6-.7 1.1-1.3 1.2zm.7 11.8c.1-.5.6-.9 1.1-.9.5 0 .8.3.7.8-.1.5-.6.9-1.2.9-.4.1-.7-.3-.6-.8zm1.8-3.5c-.5 0-.9-.4-.8-.9.1-.5.7-1 1.2-1 .6 0 .9.3.8.9-.1.5-.7.9-1.2 1zm1.1-4.5c-.6.1-.9-.3-.8-.9.1-.5.7-1 1.3-1.1.6-.1.9.3.8.9-.2.5-.7 1.1-1.3 1.1zm.8 12.3c.1-.4.6-.8 1.1-.8.5 0 .8.3.6.8-.1.4-.6.8-1.1.8-.5 0-.7-.3-.6-.8zm.2-16.7c-.6.1-1-.3-.8-.9.1-.6.7-1.1 1.3-1.2.6-.1 1 .3.9.9-.2.5-.8 1.1-1.4 1.2zm-2.3-12.7c.2-.6.8-1.1 1.4-1.3.6-.2 1 .2.9.8-.1.6-.8 1.2-1.4 1.3-.7.1-1.1-.2-.9-.8zm-1 4c.1-.6.8-1.1 1.4-1.3.6-.1 1 .2.9.8-.1.6-.8 1.2-1.4 1.3-.7.2-1.1-.2-.9-.8zm.3 3c.6-.1 1 .3.9.9-.1.6-.8 1.1-1.4 1.2-.6.1-1-.3-.8-.9.1-.6.7-1.1 1.3-1.2zm-3.6-6.1c.2-.6.8-1.1 1.4-1.3.6-.1 1 .2.8.8-.2.6-.8 1.2-1.4 1.3-.6.2-.9-.2-.8-.8zm-1 3.9c.2-.6.8-1.1 1.4-1.2.6-.1 1 .2.8.8-.2.6-.8 1.1-1.4 1.2-.6.2-1-.2-.8-.8zm.2 2.9c.6-.1 1 .3.8.9-.1.6-.8 1.1-1.4 1.2-.6.1-1-.3-.8-.9.2-.6.9-1.1 1.4-1.2zm-3.3-6c.2-.5.8-1.1 1.4-1.2.6-.1 1 .2.8.8-.2.6-.8 1.1-1.4 1.2-.6.2-1-.2-.8-.8zM102 7.3c.2-.6.8-1.1 1.4-1.2.6-.1 1 .3.8.8-.2.6-.8 1.1-1.4 1.2-.7.2-1-.2-.8-.8zm.2 2.7c.6-.1 1 .3.8.9-.2.6-.8 1.1-1.4 1.2-.6.1-.9-.3-.8-.9.2-.6.8-1.1 1.4-1.2zm-3.1-5.8c.2-.5.8-1 1.4-1.1.6-.1.9.2.8.8-.2.5-.8 1.1-1.4 1.2-.7 0-1-.4-.8-.9zm-2.7-2.9c.2-.5.8-1 1.4-1.1.6-.1.9.2.7.7-.2.5-.8 1-1.4 1.1-.6.2-.9-.2-.7-.7zm-1.3 3.5c.2-.5.8-1 1.4-1.1.6-.1.9.3.7.8-.2.5-.8 1-1.4 1.1-.5.1-.9-.3-.7-.8zm-2.5-2.9c.2-.5.8-.9 1.4-1 .6-.1.9.2.7.7-.2.5-.8 1-1.4 1-.6.1-.9-.2-.7-.7zm-1.3 3.3c.2-.5.8-1 1.4-1 .6-.1.9.3.7.8-.2.5-.8 1-1.4 1-.6.1-.9-.3-.7-.8zm-2.5-2.9c.2-.5.8-.9 1.4-1 .6-.1.8.3.6.7-.2.5-.8.9-1.4 1-.5.2-.8-.2-.6-.7zm-1.3 3.3c.2-.5.8-.9 1.4-1 .6-.1.9.3.7.8-.2.5-.8 1-1.4 1-.6 0-.9-.3-.7-.8zm-2.4-2.9c.2-.5.8-.9 1.4-.9.5-.1.8.2.6.7-.2.5-.8.9-1.4.9-.5.1-.8-.2-.6-.7zm-1.4 3.2c.2-.5.8-.9 1.4-.9.6 0 .8.3.6.8-.2.5-.8.9-1.4 1-.5-.1-.8-.4-.6-.9zM81.4 3c.2-.4.8-.8 1.4-.9.5 0 .8.3.6.7-.2.5-.8.9-1.4.9-.5.1-.8-.3-.6-.7zM80 6.1c.2-.5.8-.9 1.4-.9.5 0 .8.3.6.8-.2.5-.8.9-1.4.9-.5 0-.8-.3-.6-.8zm0 2.3c.6 0 .8.4.6.8-.2.5-.8.9-1.4.9-.6 0-.8-.4-.6-.9.3-.4.9-.8 1.4-.8zm-2.2-5.2c.2-.4.8-.8 1.4-.8.5 0 .8.3.6.7-.2.5-.8.8-1.4.9-.5 0-.8-.4-.6-.8zm-1.4 3c.2-.5.8-.8 1.4-.9.5 0 .8.3.6.8-.3.5-.9.9-1.4.9-.6.1-.8-.3-.6-.8zm-.1 2.3c.5 0 .8.4.6.8-.2.5-.8.9-1.4.9-.5 0-.8-.4-.6-.9.3-.4.9-.8 1.4-.8zm-2.1-5.2c.2-.4.8-.8 1.4-.8.5 0 .8.3.6.7-.2.4-.8.8-1.4.8-.6.1-.8-.3-.6-.7zm-1.5 3c.2-.5.8-.8 1.4-.8.5 0 .8.3.6.8-.2.5-.8.9-1.4.9-.5-.1-.8-.4-.6-.9zm-2.1-2.9c.3-.4.9-.8 1.4-.8.5 0 .8.3.5.8-.2.4-.8.8-1.4.8-.5 0-.7-.4-.5-.8zm-.1 2.1c.5 0 .8.3.6.8-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.8.2-.4.8-.8 1.4-.8zM67 3.4c.2-.4.9-.8 1.4-.8.6 0 .8.4.6.8-.2.4-.9.8-1.4.8-.5 0-.8-.4-.6-.8zm-.1 2.1c.5 0 .8.4.6.8-.2.5-.8.8-1.4.8-.5 0-.8-.4-.6-.8.2-.4.8-.8 1.4-.8zm-3.4-2.1c.2-.4.9-.7 1.4-.7.5 0 .8.3.5.8-.2.4-.9.8-1.4.8-.5-.1-.8-.5-.5-.9zm-.2 2.1c.5 0 .8.4.5.8-.2.4-.9.8-1.4.8-.5 0-.8-.4-.6-.8.3-.4.9-.8 1.5-.8zm-3.4-2.2c.2-.4.9-.7 1.4-.7.5 0 .8.4.5.8-.2.4-.9.8-1.4.7-.5 0-.8-.4-.5-.8zm-.3 2.1c.5 0 .8.4.5.8-.2.4-.9.8-1.4.8-.5 0-.8-.4-.5-.8.3-.4.9-.8 1.4-.8zm-3.3-2.2c.3-.4.9-.7 1.4-.7.5 0 .8.4.5.8-.2.4-.9.7-1.4.7-.6 0-.8-.4-.5-.8zM56 5.3c.5 0 .8.4.5.8-.2.4-.9.8-1.4.8-.5 0-.8-.4-.5-.8.2-.4.9-.8 1.4-.8zm-3.4-2.2c.3-.4.9-.7 1.4-.7.5 0 .8.4.5.8-.3.4-.9.7-1.4.7-.5 0-.7-.4-.5-.8zm-.3 2.1c.5 0 .8.4.5.8-.2.4-.9.8-1.4.8-.5 0-.8-.4-.5-.8.2-.5.9-.8 1.4-.8zM49 2.9c.3-.4.9-.7 1.5-.7.5 0 .8.4.5.8-.3.4-.9.7-1.5.7s-.8-.4-.5-.8zm-.4 2.2c.5 0 .8.4.5.8-.3.4-.9.8-1.4.7-.5 0-.8-.4-.5-.8.2-.4.9-.7 1.4-.7zm-3.3-2.4c.3-.4.9-.7 1.5-.7.5 0 .7.4.5.8-.3.4-.9.7-1.4.7-.7 0-.9-.4-.6-.8zm-.5 2.2c.5 0 .7.4.5.8-.3.4-.9.7-1.4.7-.5 0-.8-.4-.5-.8.3-.4.9-.7 1.4-.7zm-3.3-2.4c.3-.4.9-.7 1.5-.7.5 0 .7.4.5.8-.4.4-1 .7-1.5.7-.6 0-.8-.4-.5-.8zM41 4.8c.5 0 .7.4.5.8-.3.4-.9.7-1.4.7-.5 0-.8-.4-.5-.8.2-.5.9-.8 1.4-.7zm-3.3-2.5c.3-.4.9-.7 1.4-.6.5 0 .7.4.5.7-.3.4-.9.7-1.4.6-.6 0-.8-.3-.5-.7zm-.6 2.3c.5 0 .7.4.5.8-.3.4-.9.7-1.4.7-.5 0-.7-.4-.5-.8.3-.4.9-.7 1.4-.7zm-3.3-2.5c.3-.4.9-.7 1.4-.6.5 0 .7.4.4.7-.3.4-.9.7-1.4.6-.5 0-.7-.4-.4-.7zm-.7 2.3c.5 0 .7.4.5.8-.3.4-.9.7-1.4.7-.5 0-.7-.4-.5-.8.3-.4.9-.7 1.4-.7zm-3.3-2.6c.3-.4.9-.6 1.4-.6.5 0 .7.3.4.7-.3.4-.9.6-1.4.6-.5 0-.7-.3-.4-.7zm-.1 6.4c.2-.4.9-.7 1.4-.7.5 0 .7.4.5.8-.2.4-.8.7-1.4.7-.5 0-.7-.3-.5-.8zm-.7-4c.5 0 .7.4.5.7-.3.4-.9.7-1.4.7-.5 0-.7-.4-.5-.8.3-.3.9-.6 1.4-.6zm-3.3-2.6c.2-.4.9-.6 1.4-.6.5 0 .7.3.4.7-.3.4-.9.6-1.4.6-.5-.1-.7-.4-.4-.7zm-.1 6.5c.2-.4.9-.7 1.4-.7.5 0 .7.4.5.7-.2.4-.8.7-1.3.7-.6.1-.8-.3-.6-.7zm-.1 3.5c-.2.4-.8.7-1.3.7s-.7-.3-.5-.8c.2-.4.8-.7 1.3-.7s.7.4.5.8zM24.8 4c.5 0 .7.3.4.7-.3.4-.9.7-1.4.6-.5 0-.7-.3-.5-.7.4-.3 1-.6 1.5-.6zm-2.9-2.9c.3-.4.9-.6 1.3-.6.5 0 .6.3.4.7-.3.4-.9.6-1.3.6-.5 0-.7-.4-.4-.7zm.8 6.2c.5 0 .7.3.5.7-.2.4-.8.7-1.3.7s-.7-.3-.5-.7c.2-.4.8-.7 1.3-.7zm-1.8-3.6c.5 0 .6.4.4.7-.3.4-.9.7-1.3.7-.5 0-.7-.4-.4-.7.2-.4.8-.7 1.3-.7zM17.7.8c.3-.4.9-.6 1.3-.6.5 0 .6.3.3.7-.3.3-.8.6-1.3.6-.4-.1-.6-.4-.3-.7zm-.4 7c.2-.4.8-.7 1.3-.7s.6.3.4.7c-.2.4-.8.7-1.3.7-.4 0-.6-.3-.4-.7zm1.8 7.4c-.2.4-.7.7-1.2.7s-.7-.3-.5-.7c.2-.4.8-.7 1.2-.7.5 0 .7.3.5.7zM17.2 19c-.2.4-.7.7-1.1.7-.5 0-.7-.3-.5-.7.2-.4.7-.7 1.2-.7.4 0 .6.3.4.7zM15.3 4.1c.3-.4.8-.6 1.3-.6s.6.3.4.7c-.2.4-.8.6-1.3.6s-.7-.3-.4-.7zm-.1 7.4c.2-.4.8-.7 1.2-.7.5 0 .6.3.4.7-.2.4-.8.7-1.2.7-.5 0-.7-.3-.4-.7zm-.5 3.8c-.2.4-.7.7-1.1.7-.4 0-.6-.3-.4-.7.2-.4.7-.7 1.2-.7.3 0 .5.3.3.7zm-1.8-7.6c.2-.4.8-.7 1.3-.6.5 0 .6.3.4.7-.2.4-.8.7-1.2.7-.5-.1-.7-.4-.5-.8zm-.2 11.6c-.2.4-.7.7-1.1.7-.4 0-.6-.3-.5-.7.2-.4.7-.7 1.1-.7.5 0 .7.3.5.7zM10.8 3.9c.3-.4.8-.6 1.3-.6s.6.3.4.7c-.2.4-.8.6-1.3.6s-.7-.3-.4-.7zm-.1 7.6c.2-.4.8-.7 1.2-.7.4 0 .6.3.4.7-.2.4-.8.7-1.2.7-.4 0-.6-.3-.4-.7zM8.3 7.6c.2-.4.8-.6 1.3-.6.4 0 .6.3.4.6-.3.4-.8.7-1.3.7-.4 0-.6-.3-.4-.7zM8 19.5c-.2.4-.6.7-1.1.7-.4 0-.6-.2-.4-.6.2-.4.7-.7 1.1-.7.4 0 .6.3.4.6zM6.1 3.7c.2-.3.8-.6 1.3-.6.4 0 .6.3.4.6-.4.4-.9.7-1.4.7-.4-.1-.6-.3-.3-.7zM6 11.5c.2-.4.8-.7 1.2-.7.4 0 .6.3.4.7-.2.4-.7.7-1.2.7-.4 0-.6-.3-.4-.7zM3.5 7.6c.2-.3.8-.6 1.2-.6.4 0 .6.3.4.6-.2.3-.8.6-1.2.6-.4 0-.6-.3-.4-.6zM1 3.1c.2-.3.8-.6 1.2-.5.4 0 .6.3.3.6-.2.3-.7.6-1.1.5-.5 0-.6-.3-.4-.6zm.1 8.5c.2-.3.7-.6 1.1-.6.4 0 .6.3.4.6-.2.3-.7.6-1.1.7-.5 0-.7-.3-.4-.7zm1.1 21c-.1.2-.3.3-.4.4-.2 0-.3-.1-.2-.2.1-.2.3-.3.4-.4.1-.1.2.1.2.2zM3 19.9c-.1.3-.5.5-.8.6-.3 0-.5-.2-.4-.5.1-.3.5-.5.8-.6.4 0 .5.2.4.5zm1 8.3c-.1.2-.4.4-.6.5-.3 0-.4-.1-.3-.4.1-.2.4-.4.6-.5.2 0 .4.2.3.4zm-.2-12.5c.1-.4.7-.7 1.1-.7.4 0 .6.3.4.6-.2.4-.7.7-1.1.7-.4 0-.6-.3-.4-.6zM5 36.5c-.1 0-.2-.1-.2-.2.1-.1.2-.3.4-.3.1 0 .2.1.2.2-.1.1-.2.2-.4.3zm.9-12.7c-.1.3-.5.5-.8.6-.3 0-.5-.2-.4-.5.1-.3.5-.5.8-.6.4 0 .5.2.4.5zm1.2 8.1c-.1.2-.4.5-.6.5-.3 0-.4-.1-.3-.4.1-.2.4-.5.6-.5.3 0 .4.1.3.4zm.7-4.2c.1-.3.4-.5.7-.5.3 0 .4.2.3.4-.1.3-.4.5-.7.5-.3.1-.5-.1-.3-.4zm1.1 11.9c-.1.2-.3.4-.5.4s-.3-.1-.3-.3c.1-.2.3-.4.5-.4s.3.1.3.3zm-.4-24.1c.2-.4.7-.7 1.2-.7.4 0 .6.3.4.7-.2.4-.7.7-1.2.7-.4 0-.6-.3-.4-.7zm1.8 19.9c-.1.2-.3.4-.6.5-.3 0-.4-.1-.3-.3.1-.2.3-.4.6-.5.3-.1.4 0 .3.3zm-.5-11.3c-.4 0-.6-.2-.4-.6.2-.4.6-.7 1-.7s.6.2.4.6c-.2.3-.6.7-1 .7zm1 7.2c.1-.3.4-.5.8-.6.3 0 .5.2.4.5-.1.3-.4.5-.8.6-.4 0-.5-.2-.4-.5zm1.4 11.6c-.1.2-.2.3-.4.4-.2 0-.3-.1-.2-.2 0-.2.2-.3.4-.4.2 0 .3.1.2.2zm1.4-4c-.1.2-.3.4-.5.4s-.4-.1-.3-.3c.1-.2.3-.4.5-.4.2-.1.3.1.3.3zm0-11.9c-.1.3-.6.6-.9.7-.4 0-.6-.2-.5-.6.1-.3.6-.7 1-.7s.6.3.4.6zm1.4 7.8c-.1.2-.4.5-.6.5-.3 0-.4-.1-.3-.4.1-.2.4-.5.6-.5.2 0 .4.1.3.4zm-.7-11.1c-.4 0-.7-.3-.5-.6.2-.4.6-.7 1.1-.7.4 0 .6.3.5.6-.2.3-.7.6-1.1.7zm1 7.1c.1-.3.5-.6.9-.7.4 0 .6.2.4.5-.1.3-.5.6-.9.7-.3.1-.5-.2-.4-.5zm1.5 11.4c-.1.2-.3.3-.5.4-.2 0-.3-.1-.3-.3.1-.2.3-.3.5-.4.2 0 .3.1.3.3zm1.3-3.9c-.1.2-.3.4-.6.4-.2 0-.4-.1-.3-.3.1-.2.3-.4.6-.5.3 0 .4.1.3.4zm.1-11.6c-.1.4-.6.7-1 .7s-.6-.2-.5-.6c.1-.4.6-.7 1-.7.5-.1.7.2.5.6zm.1-3.9c.2-.4.7-.7 1.1-.7.4 0 .7.3.5.7-.2.4-.7.7-1.1.7-.4 0-.6-.3-.5-.7zm.1 11.6c.1-.3.5-.6.8-.6.3 0 .5.2.4.5-.1.3-.5.6-.8.6-.3 0-.5-.2-.4-.5zm1.6 11c-.1.2-.3.4-.5.4s-.3-.1-.3-.3c.1-.2.3-.4.5-.4s.4.1.3.3zm-.2-15c.1-.3.5-.6.9-.7.4 0 .6.2.5.6-.2.4-.6.7-1 .7s-.6-.2-.4-.6zm1.5 11.2c-.1.2-.3.4-.5.4s-.4-.1-.3-.3c.1-.2.3-.4.6-.4.1 0 .2.1.2.3zm.2-3.7c.1-.3.4-.5.7-.6.3 0 .5.2.4.4-.1.3-.4.5-.7.6-.3.1-.5-.1-.4-.4zm1.6 10.5c0 .1-.2.3-.4.3s-.3-.1-.2-.2c.1-.1.2-.3.4-.3.1 0 .2.1.2.2zM22.8 34c.1-.3.5-.6.9-.6s.6.2.4.5c-.1.3-.5.6-.8.6-.4.1-.7-.2-.5-.5zm1.5 10.8c-.1.2-.3.4-.5.4s-.4-.1-.3-.3c.1-.2.3-.4.5-.4.3 0 .4.1.3.3zm-.2-14.7c.1-.4.6-.7 1-.7s.6.3.5.6c-.1.4-.6.7-1 .7-.4.1-.7-.2-.5-.6zm1.5 11c-.1.2-.3.4-.6.5-.3 0-.4-.1-.3-.4.1-.2.3-.4.6-.5.2 0 .3.2.3.4zm.2-3.6c.1-.3.4-.5.8-.6.3 0 .5.2.4.5-.1.3-.4.5-.8.6-.3 0-.5-.2-.4-.5zm1.5 10.3c-.1.2-.3.3-.4.3-.2 0-.3-.1-.3-.2.1-.2.3-.3.4-.3.2 0 .3.1.3.2zM27 33.7c.1-.3.5-.6.9-.6s.6.2.5.6c-.1.3-.5.6-.9.6s-.6-.3-.5-.6zm1.5 10.6c-.1.2-.3.4-.6.4s-.4-.1-.3-.3c.1-.2.3-.4.6-.4s.4.1.3.3zm.3-3.5c.1-.3.4-.5.7-.5.3 0 .5.2.4.4-.1.3-.4.5-.7.5-.4.1-.5-.1-.4-.4zm1 10.2c-.2 0-.2-.1-.2-.2s.2-.2.4-.3c.2 0 .2.1.2.2-.1.1-.3.2-.4.3zm.1-13.8c.1-.3.5-.6.8-.6.3 0 .5.2.4.5-.1.3-.5.6-.8.6-.3 0-.5-.2-.4-.5zm1.5 10.2c-.1.2-.3.3-.5.3s-.3-.1-.3-.3c.1-.2.3-.3.5-.4.2.1.3.2.3.4zm-.3-14c.1-.3.5-.6.9-.7.4 0 .6.2.5.6-.1.4-.5.7-.9.7-.4.1-.6-.2-.5-.6zM32.6 44c-.1.2-.3.4-.6.4s-.4-.1-.3-.4c.1-.2.3-.4.6-.4s.4.1.3.4zm.2-3.5c.1-.3.4-.5.7-.5.3 0 .5.2.4.5-.1.3-.4.5-.7.5-.3 0-.5-.2-.4-.5zm1 10.1c-.2 0-.3-.1-.2-.2 0-.1.2-.3.4-.3s.3.1.2.2c-.1.1-.3.2-.4.3zm.2-13.7c.1-.3.5-.6.8-.6.3 0 .5.2.4.5-.1.3-.5.6-.8.6-.3.1-.5-.2-.4-.5zM35.4 47c-.1.2-.3.3-.5.4-.2 0-.3-.1-.3-.3.1-.2.3-.3.5-.4.2 0 .4.2.3.3zm.3-3.3c.1-.2.4-.4.6-.5.3 0 .4.2.3.4-.1.2-.4.4-.6.5-.2.1-.4-.1-.3-.4zm.9 9.5c-.1 0-.2-.1-.2-.1 0-.1.2-.2.3-.2.1 0 .2.1.2.2-.1 0-.2.1-.3.1zm.2-12.9c.1-.3.4-.5.7-.5.3 0 .5.2.4.5-.1.3-.4.5-.7.5-.3 0-.5-.2-.4-.5zm1.3 9.7c-.1.1-.2.3-.4.3s-.3-.1-.2-.2c.1-.1.2-.3.4-.3.2-.1.3 0 .2.2zM38 36.7c.1-.3.5-.6.9-.6s.6.2.4.6c-.1.3-.5.6-.8.6-.4 0-.6-.2-.5-.6zm1.4 10.1c-.1.2-.3.4-.5.4s-.4-.1-.3-.3c.1-.2.3-.4.5-.4.2-.1.3.1.3.3zm.2-3.3c.1-.2.4-.5.7-.5.3 0 .4.2.4.4-.1.2-.4.4-.7.5-.3.1-.5-.1-.4-.4zm.8 9.4c-.1 0-.2-.1-.2-.2s.2-.2.3-.2c.1 0 .2.1.2.2s-.2.2-.3.2zm.4-12.8c.1-.3.4-.5.8-.5.3 0 .5.2.4.5-.1.3-.4.5-.8.5s-.5-.2-.4-.5zm1.2 9.7c0 .1-.3.2-.4.2-.2 0-.3-.1-.2-.3.1-.2.3-.3.5-.3.1.1.2.2.1.4zm-.1-13.2c.1-.3.5-.6.9-.6s.6.3.5.6c-.1.3-.5.6-.9.6s-.6-.2-.5-.6zm1.4 10c-.1.2-.3.4-.6.4-.2 0-.4-.1-.3-.3.1-.2.3-.4.6-.4.2 0 .4.1.3.3zm.9 6.2c-.1 0-.2-.1-.2-.2s.2-.2.3-.2c.1 0 .2.1.2.2s-.1.2-.3.2zm.4-9.4c-.1.2-.4.4-.7.5-.3 0-.4-.2-.4-.4.1-.2.4-.5.7-.5.3-.1.5.1.4.4zm0-10.3c-.1.4-.6.7-1 .7s-.6-.3-.5-.7c.1-.4.6-.7 1-.7s.6.3.5.7zm.1 6.9c.1-.3.5-.5.8-.5.3 0 .5.2.4.5-.1.3-.5.5-.8.5-.4 0-.5-.2-.4-.5zm1.2 9.6c-.1.2-.3.3-.5.3s-.3-.1-.2-.3c.1-.2.3-.3.5-.3.1 0 .2.2.2.3zm1.2-3.1c-.1.2-.3.4-.6.4-.2 0-.4-.2-.3-.4.1-.2.3-.4.6-.4.3.1.4.2.3.4zm.1-9.9c-.1.3-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.6s.6.3.5.6zm.8 16.1c-.1 0-.2-.1-.2-.2s.2-.2.4-.2.2.1.2.2c-.1.1-.3.2-.4.2zm.4-9.4c-.1.2-.4.5-.7.5-.3 0-.5-.2-.4-.4.1-.3.4-.5.7-.5.4 0 .5.2.4.4zm1.3 6.3c-.1.2-.3.3-.5.3s-.3-.1-.2-.3c.1-.2.3-.3.5-.3.1 0 .2.1.2.3zm0-9.6c-.1.3-.5.5-.8.5-.3 0-.5-.2-.4-.5.1-.3.5-.5.8-.5.3 0 .5.2.4.5zm1.3 6.5c-.1.2-.4.4-.6.4-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.4.2 0 .4.2.3.4zm0-9.9c-.1.3-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.6.5 0 .7.3.5.6zm.8 16.1c-.2 0-.2-.1-.2-.2.1-.1.2-.2.4-.2s.2.1.2.2c-.1.1-.3.2-.4.2zm.5-9.4c-.1.3-.4.5-.7.5-.3 0-.5-.2-.4-.5.1-.3.4-.5.7-.5.3.1.5.3.4.5zm1.2 6.3c-.1.2-.3.3-.5.3s-.3-.1-.3-.3c.1-.2.3-.3.5-.3s.3.1.3.3zm.1-9.5c-.1.3-.5.5-.8.5-.3 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.3 0 .5.3.4.6zm1.2 6.5c-.1.2-.4.4-.6.4-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.4.2 0 .4.2.3.4zm.1-9.9c-.1.3-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.6s.6.2.5.6zm.6 16c-.2 0-.2-.1-.2-.2.1-.1.2-.2.4-.2s.2.1.2.2c-.1.2-.2.3-.4.2zm.6-9.3c-.1.3-.4.5-.7.5-.3 0-.5-.2-.4-.5.1-.3.4-.5.7-.5.3 0 .5.3.4.5zm1.1 6.3c-.1.2-.3.3-.5.3s-.3-.1-.3-.3c.1-.2.3-.3.5-.3.3 0 .4.1.3.3zm.2-9.5c-.1.3-.5.5-.8.5-.3 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.3 0 .5.3.4.6zm1.2 6.5c-.1.2-.4.4-.6.4-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.4.2 0 .4.2.3.4zm.1-9.9c-.1.3-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.6s.6.3.5.6zm.5 16.1c-.2 0-.2-.1-.2-.2.1-.1.2-.2.4-.2s.2.1.2.2-.2.2-.4.2zm.7-9.3c-.1.3-.4.5-.7.4-.3 0-.5-.2-.4-.5.1-.3.4-.5.7-.5.3.1.5.3.4.6zm1.1 6.3c-.1.2-.3.3-.5.3s-.3-.2-.3-.3c.1-.2.3-.3.5-.3.3 0 .4.1.3.3zm.2-9.6c-.1.3-.5.5-.8.5-.4 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.4 0 .5.3.4.6zm1.2 6.6c-.1.2-.4.4-.6.4-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.4.2 0 .4.2.3.4zm.1-10c-.1.3-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6.4.1.7.4.5.7zm.5 16.2c-.2 0-.2-.1-.2-.2.1-.1.2-.2.4-.2s.2.1.2.2c-.1.1-.2.2-.4.2zm.7-9.3c-.1.3-.4.5-.7.4-.3 0-.5-.2-.4-.5.1-.3.4-.5.7-.4.4 0 .5.2.4.5zm1.1 6.3c-.1.2-.3.3-.5.3s-.3-.2-.3-.3c.1-.2.3-.3.5-.3.3 0 .4.1.3.3zm.3-9.6c-.1.3-.5.5-.9.5s-.5-.3-.4-.6c.1-.3.5-.5.9-.5.3 0 .5.3.4.6zm1.1 6.6c-.1.2-.4.4-.6.3-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.4.2.1.4.3.3.5zm.2-10c-.1.4-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6.4.1.6.4.5.7zm.4 16.3c-.2 0-.2-.1-.2-.2.1-.2.2-.2.4-.2s.2.1.2.2c-.1.1-.3.2-.4.2zm.8-9.4c-.1.3-.4.5-.8.4-.3 0-.5-.2-.4-.5.1-.3.4-.5.8-.4.3 0 .5.2.4.5zm1 6.4c-.1.2-.3.3-.5.3s-.3-.2-.3-.3c.1-.2.3-.3.5-.3.3 0 .4.1.3.3zm.3-9.7c-.1.3-.5.5-.9.5s-.6-.3-.4-.6c.1-.3.5-.5.9-.5.3 0 .5.3.4.6zm1.1 6.7c-.1.2-.4.4-.6.3-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.3.3 0 .4.2.3.4zm.2-10.1c-.1.3-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6.4.1.6.4.5.7zm.4 16.4c-.2 0-.2-.1-.2-.2.1-.1.2-.2.4-.2s.2.1.2.2c-.1.2-.2.2-.4.2zm.8-9.4c-.1.3-.4.5-.8.4-.3 0-.5-.3-.4-.5.1-.3.4-.5.8-.4.3 0 .5.2.4.5zm1 6.4c-.1.2-.3.3-.5.2-.2 0-.3-.2-.2-.3.1-.2.3-.3.5-.2.2 0 .3.2.2.3zm.4-9.7c-.1.3-.5.5-.9.5s-.6-.3-.4-.6c.1-.3.5-.5.9-.5.3 0 .5.3.4.6zm1.1 6.7c-.1.2-.4.4-.6.3-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.3.2.1.4.2.3.4zm.2-10.1c-.1.4-.6.6-.9.6-.4 0-.6-.3-.5-.7.1-.3.5-.6.9-.6s.6.3.5.7zm.4 16.5c-.1 0-.2-.1-.2-.2.1-.1.2-.2.4-.2.1 0 .2.1.2.2-.1.2-.3.3-.4.2zm.8-9.5c-.1.3-.4.4-.8.4-.3 0-.5-.3-.4-.5.1-.3.4-.4.7-.4.4 0 .6.2.5.5zm1 6.5c-.1.2-.3.3-.5.2-.2 0-.3-.2-.2-.3.1-.2.3-.3.5-.2.2.1.3.2.2.3zm.4-9.8c-.1.3-.5.5-.9.5s-.5-.3-.4-.6c.1-.3.5-.5.9-.5.3 0 .5.3.4.6zm1.1 6.8c-.1.2-.4.3-.6.3-.3 0-.4-.2-.3-.4.1-.2.4-.3.6-.3.2 0 .4.2.3.4zm.2-10.3c-.1.3-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6.4.1.6.4.5.7zm.4 16.8c-.1 0-.2-.1-.2-.2.1-.1.2-.2.4-.2.1 0 .2.1.2.2-.1.1-.3.2-.4.2zm.8-9.7c-.1.3-.4.4-.8.4-.3 0-.5-.3-.4-.5.1-.3.4-.4.7-.4.5 0 .6.3.5.5zm1.1 6.7c-.1.2-.3.3-.5.2-.2 0-.3-.2-.2-.3.1-.2.3-.3.5-.2.1 0 .2.1.2.3zm.3-10c-.1.3-.5.5-.8.5-.3 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.3 0 .5.3.4.6zm1.2 7c-.1.2-.4.3-.6.3-.2 0-.4-.2-.3-.4.1-.2.4-.3.6-.3.2 0 .3.2.3.4zm.2-10.5c-.1.4-.6.6-.9.6-.4 0-.6-.3-.5-.7.1-.4.5-.6.9-.6s.6.3.5.7zm.3 17c-.1 0-.2-.1-.2-.2.1-.1.2-.2.3-.1.1 0 .2.1.2.2s-.1.1-.3.1zm.9-9.8c-.1.2-.4.4-.7.4-.3 0-.5-.3-.4-.5.1-.2.4-.4.7-.4.4 0 .5.3.4.5zm-.9-10.1c-.4 0-.7-.4-.5-.8.1-.4.6-.7 1-.7s.7.4.5.8c-.1.4-.6.7-1 .7zm2 16.9c-.1.1-.3.2-.5.2s-.3-.2-.2-.3c.1-.1.3-.2.5-.2.1 0 .2.2.2.3zm.3-10.2c-.1.3-.5.5-.8.5-.4 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.4 0 .5.3.4.6zm1.2 7.1c-.1.2-.4.3-.6.3-.2 0-.4-.2-.3-.4.1-.2.4-.3.6-.3.3 0 .4.2.3.4zm.2-10.6c-.1.4-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6s.6.3.5.7zm.4 17.3c-.1 0-.2-.1-.1-.2 0-.1.2-.1.3-.1.1 0 .2.1.1.2 0 0-.2.1-.3.1zm.9-10c-.1.2-.4.4-.7.4-.3 0-.5-.3-.4-.5.1-.2.4-.4.7-.4.3.1.5.3.4.5zm0-11c-.1.4-.6.7-1 .7s-.7-.4-.5-.8c.1-.4.6-.7 1-.7.4.1.7.4.5.8zm1.1 17.9c-.1.1-.3.2-.5.2s-.3-.2-.2-.3c.1-.1.3-.2.5-.2.1.1.2.2.2.3zm.3-10.3c-.1.3-.5.5-.8.5-.3 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.3 0 .5.3.4.6zm1.2 7.2c-.1.2-.3.3-.6.3-.2 0-.4-.2-.3-.4.1-.2.3-.3.6-.3.3.1.4.2.3.4zm.2-10.8c-.1.4-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6s.6.3.5.7zm1.4 7.5c-.1.2-.4.4-.7.4-.3 0-.5-.3-.4-.5.1-.2.4-.4.7-.4.3 0 .5.2.4.5zm0-11.3c-.1.4-.6.7-1 .7s-.7-.4-.6-.8c.1-.4.6-.7 1-.7.4.1.7.4.6.8zm1 18.3c-.1.1-.3.2-.4.2-.2 0-.3-.2-.2-.3.1-.1.3-.2.4-.2.2.1.3.2.2.3zm.4-10.6c-.1.3-.5.5-.8.5-.3 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.3.1.5.4.4.6zm1.3 7.4c-.1.2-.3.3-.6.3-.2 0-.3-.2-.3-.4.1-.2.3-.3.6-.3.2.1.3.3.3.4zm.1-11c-.1.3-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6s.7.3.5.7zm1.4 7.6c-.1.3-.4.4-.7.4-.3 0-.4-.2-.4-.5.1-.2.4-.4.7-.4.4.1.5.3.4.5zm-.4-15.5c.1-.4.6-.8 1.1-.8.5 0 .8.4.6.8-.1.4-.6.8-1.1.8-.5 0-.7-.3-.6-.8zM96.4 54c-.2 0-.2-.1-.2-.3.1-.1.2-.2.4-.2s.2.1.2.3c0 .2-.2.3-.4.2zm.8-11c-.1.3-.5.5-.8.5-.3 0-.5-.3-.4-.6.1-.3.5-.5.8-.5.3.1.5.3.4.6zm1.3 7.6c-.1.2-.3.3-.5.3s-.3-.2-.3-.4c.1-.2.3-.3.5-.3.3.1.4.2.3.4zm.1-11.4c-.1.3-.5.6-.9.6s-.6-.3-.5-.7c.1-.3.5-.6.9-.6.4.1.7.4.5.7zm-.1-4c.1-.4.6-.7 1-.7s.7.4.6.7c-.1.4-.6.7-1 .7-.5.1-.8-.3-.6-.7zm1.6 11.9c-.1.2-.4.4-.7.4-.3 0-.4-.2-.3-.5.1-.2.4-.4.7-.4.3.1.4.3.3.5zm-.5-15.9c.1-.4.6-.8 1.1-.8.5 0 .8.4.6.8-.1.4-.6.8-1.1.8-.4 0-.7-.3-.6-.8zm1.3 23.5c-.2 0-.2-.1-.2-.2.1-.1.2-.2.4-.2s.2.1.2.2c-.1.2-.3.2-.4.2zm.7-11.3c-.1.3-.5.5-.8.4-.3 0-.5-.3-.4-.6.1-.3.4-.5.8-.5.4.2.5.4.4.7zm1.4 7.8c-.1.2-.3.3-.5.2-.2 0-.3-.2-.2-.3.1-.2.3-.3.5-.2.1 0 .3.2.2.3zm.1-11.7c-.1.3-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.6s.6.3.5.6zm-.2-4.1c.1-.4.6-.7 1-.7s.7.3.6.7c-.1.4-.6.7-1 .7s-.7-.3-.6-.7zm1.7 12.2c-.1.2-.4.4-.7.3-.3 0-.4-.2-.3-.4.1-.2.4-.4.6-.3.4 0 .5.2.4.4zm-.5-16.3c.1-.4.6-.8 1.1-.8.5 0 .8.4.6.8-.1.4-.6.8-1.1.8-.4 0-.7-.4-.6-.8zm1.4 24.1c-.1 0-.2-.1-.2-.2s.2-.2.3-.1c.1 0 .2.1.2.2s-.2.1-.3.1zm.7-11.6c-.1.3-.4.5-.8.4-.3 0-.5-.3-.4-.5.1-.3.4-.5.8-.4.3 0 .5.2.4.5zm1.4 8c-.1.1-.3.2-.5.2s-.3-.2-.2-.3c.1-.1.3-.2.5-.2s.3.2.2.3zm.1-12c-.1.3-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.6s.6.3.5.6zm-.1-4.2c.1-.4.6-.7 1-.7s.7.3.6.7c-.1.4-.6.7-1 .7-.5 0-.7-.4-.6-.7zm1.7 12.5c-.1.2-.4.3-.6.3-.3 0-.4-.2-.3-.4.1-.2.4-.3.6-.3.3 0 .4.2.3.4zm-.5-16.8c.1-.4.6-.8 1.1-.8.5 0 .8.3.6.8-.1.4-.6.8-1.1.8-.5 0-.8-.4-.6-.8zm2.2 12.9c-.1.3-.4.5-.7.4-.3 0-.5-.3-.4-.5.1-.3.4-.5.7-.4.3 0 .5.2.4.5zm1.5 8.3c-.1.1-.3.2-.4.2-.2 0-.3-.2-.2-.3.1-.1.3-.2.4-.2.1 0 .2.1.2.3zm0-12.5c-.1.3-.5.6-.9.5-.4 0-.6-.3-.5-.6.1-.3.5-.6.9-.5.4 0 .6.3.5.6zm-.1-4.3c.1-.4.5-.7 1-.7.4 0 .7.3.6.7-.1.4-.6.7-1 .7-.5 0-.7-.4-.6-.7zm1.8 13c-.1.2-.3.3-.6.3-.2 0-.4-.2-.3-.4.1-.2.3-.3.6-.3s.4.2.3.4zm1.7-4.1c-.1.3-.4.4-.7.4-.3 0-.5-.2-.4-.5.1-.3.4-.4.7-.4.3 0 .5.2.4.5zm-.5-17.1c-.5 0-.8-.3-.7-.8.1-.5.6-.9 1.1-.9.5 0 .8.3.7.8-.1.5-.6.9-1.1.9zm.8 12.7c.1-.3.5-.5.8-.5.4 0 .6.3.5.6-.1.3-.5.5-.8.5-.4 0-.6-.3-.5-.6zm.9 13.1c-.2 0-.2-.1-.2-.2.1-.1.2-.2.4-.2s.2.1.2.2c-.1.2-.2.2-.4.2zm.3-17.6c.1-.4.5-.7 1-.7.4 0 .7.3.6.7-.1.4-.5.7-1 .7-.4 0-.7-.3-.6-.7zm1.9 13.5c-.1.2-.3.3-.5.3s-.3-.2-.3-.4c.1-.2.3-.3.5-.3.3 0 .4.2.3.4zm-.1-17.3c-.5 0-.7-.3-.6-.7.1-.4.6-.8 1-.8.5 0 .8.3.6.7 0 .4-.5.7-1 .8zm1.9 13c-.1.2-.4.4-.7.4-.3 0-.5-.2-.4-.5.1-.2.4-.4.7-.4.3.1.4.3.4.5zm-.7-17.7c-.5 0-.8-.3-.7-.8.1-.5.6-.9 1.1-.9.5 0 .8.3.7.8-.1.4-.6.8-1.1.9zm2.3 13.2c-.1.3-.5.5-.8.5-.3 0-.5-.3-.5-.6.1-.3.4-.5.8-.5.3.1.6.3.5.6zm0-4.7c.1-.4.5-.7.9-.7s.7.3.6.7c-.1.4-.5.7-.9.7-.5 0-.7-.3-.6-.7zm2 14c-.1.2-.3.3-.5.3s-.3-.2-.3-.3c.1-.2.3-.3.5-.3s.4.2.3.3zm-.2-18.1c-.5 0-.7-.3-.6-.7.1-.4.6-.8 1-.8.5 0 .7.3.6.7-.1.4-.5.8-1 .8zm2 13.7c-.1.2-.4.4-.6.4-.3 0-.4-.2-.4-.4.1-.2.4-.4.6-.4.3 0 .5.2.4.4zm.3-19.5c-.1.5-.6.9-1.1.9-.5 0-.8-.3-.7-.8.1-.5.6-.9 1.1-.9.5 0 .8.3.7.8zm1.3 14.8c-.1.3-.4.5-.8.5-.3 0-.5-.3-.5-.5.1-.3.4-.5.8-.5.4-.1.6.2.5.5zm1.6-5c-.1.4-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.7.3.1.5.4.5.7zm.6 14.6c-.1.1-.3.2-.4.2-.2 0-.3-.1-.2-.3.1-.1.2-.2.4-.2.2.1.3.2.2.3zm.7-19.7c-.1.4-.6.8-1 .8-.5 0-.7-.3-.6-.7.1-.4.5-.8 1-.8.4 0 .7.3.6.7zm1.2 15.1c-.1.2-.3.4-.6.3-.3 0-.4-.2-.3-.4.1-.2.3-.4.6-.3.2 0 .4.2.3.4zm-1-19.4c-.5 0-.8-.3-.7-.7.1-.5.6-.9 1.1-.9.5-.1.8.3.7.7-.1.4-.6.8-1.1.9zm2.7 14.5c-.1.3-.4.5-.7.5-.3 0-.5-.2-.4-.5.1-.3.4-.5.7-.5.3 0 .5.2.4.5zm-.7-25c-.6.1-1-.2-.9-.8.1-.5.6-1.1 1.2-1.2.6-.1 1 .2.9.8-.1.5-.6 1-1.2 1.2zm2.3 19.8c-.1.3-.5.6-.9.6s-.6-.3-.5-.6c.1-.3.5-.6.9-.6.3 0 .5.2.5.6zm.4 15.4c-.2 0-.2-.1-.2-.2s.2-.2.4-.2.2.1.2.2c0 .2-.2.3-.4.2zm0-20c-.4 0-.7-.3-.6-.7.1-.4.5-.8 1-.8.4 0 .7.3.6.7-.1.4-.6.7-1 .8zm.4-6.2c.1-.5.6-.9 1-.9.5-.1.8.2.7.7-.1.5-.6.9-1.1.9-.4.1-.7-.2-.6-.7zm1.9 21.2c-.1.2-.3.3-.5.3s-.4-.2-.3-.3c.1-.2.3-.3.5-.3.3-.1.4.1.3.3zM138 20c-.5.1-.9-.3-.8-.8.1-.5.6-1 1.1-1.1.5-.1.9.2.8.8 0 .5-.5 1-1.1 1.1zm2 20.7c-.1.3-.4.5-.7.5-.3 0-.5-.2-.4-.5.1-.2.4-.5.7-.5.3 0 .5.2.4.5zm-1.1-26.3c-.6.1-1-.2-.9-.8.1-.5.6-1.1 1.2-1.2.6-.1 1 .2.9.8-.1.5-.6 1.1-1.2 1.2zm2.7 20.8c-.1.3-.5.6-.8.6-.4 0-.6-.2-.5-.6.1-.3.4-.6.8-.6.3 0 .6.3.5.6zm.8 16.2c-.1 0-.2-.1-.1-.2 0-.1.2-.2.3-.1.1 0 .2.1.1.2-.1 0-.2.1-.3.1zm-.3-21.1c-.4 0-.7-.2-.6-.6.1-.4.5-.7.9-.8.4 0 .7.2.6.6-.1.4-.5.7-.9.8zm1.1-5.7c-.5.1-.8-.2-.7-.7.1-.4.5-.9 1-.9.5-.1.8.2.7.7-.1.4-.5.8-1 .9zm1.5 21.5c-.1.2-.3.3-.5.3s-.3-.1-.3-.3c.1-.2.3-.3.4-.3.3 0 .4.1.4.3zm-.5-27.3c-.5.1-.9-.2-.8-.7.1-.5.6-1 1.1-1.1.5-.1.9.2.8.7-.1.5-.6 1-1.1 1.1zm2.3 21.8c-.1.2-.3.4-.6.4s-.4-.2-.4-.4c.1-.2.3-.4.6-.4s.5.2.4.4zm1.6-5.8c-.1.3-.4.6-.8.6s-.6-.2-.5-.5c.1-.3.4-.6.8-.6s.6.2.5.5zm.6-5.3c-.4 0-.7-.2-.6-.6.1-.4.5-.7.9-.8.4-.1.7.2.6.6-.1.4-.5.8-.9.8zm1.1-6c-.5.1-.8-.2-.7-.6.1-.4.5-.8 1-.9.5-.1.8.2.7.6-.1.4-.6.8-1 .9zm1.4 23c-.2 0-.3-.1-.2-.2 0-.1.2-.2.4-.2s.3.1.2.2c-.1.1-.2.2-.4.2zm-.5-29.1c-.5.1-.9-.2-.8-.7.1-.5.5-1 1.1-1.1.5-.1.9.2.9.7-.2.4-.7.9-1.2 1.1zm.7-6.3c-.6.2-1-.2-.9-.7.1-.5.5-1.1 1.1-1.3.6-.2 1 .1.9.7 0 .6-.5 1.1-1.1 1.3zm2.1 29.3c-.1.2-.3.4-.5.4s-.4-.1-.3-.3c.1-.2.3-.4.5-.4s.3.1.3.3zm.9-5.6c-.3 0-.5-.2-.5-.5.1-.3.4-.5.7-.6.3 0 .5.2.5.5 0 .4-.3.6-.7.6zm1.3-6.2c-.4.1-.6-.2-.6-.5.1-.3.4-.7.8-.7.4-.1.7.2.6.5 0 .3-.4.6-.8.7zm1.1-6.4c-.5.1-.8-.2-.7-.6.1-.4.5-.8.9-.9.5-.1.8.2.7.6 0 .4-.5.8-.9.9zm.8-6.6c-.5.1-.9-.2-.8-.6.1-.5.5-1 1-1.1.5-.1.9.1.8.6 0 .5-.4 1-1 1.1zm.7-6.6c-.6.2-1-.1-.9-.6 0-.5.5-1.1 1.1-1.3.6-.2 1 .1.9.6-.1.6-.5 1.1-1.1 1.3zm.5-6.6c-.6.2-1-.1-1-.6 0-.6.5-1.2 1.1-1.4.6-.2 1 0 1 .6s-.5 1.2-1.1 1.4zm2.2 37.7c0 .2-.2.3-.5.3-.2 0-.3-.1-.3-.3 0-.2.2-.3.4-.3.3 0 .4.2.4.3zm1-6c-.3 0-.5-.2-.4-.4.1-.3.3-.5.6-.5s.5.1.4.4c0 .2-.3.5-.6.5zm1.3-6.7c-.4.1-.6-.2-.6-.5.1-.3.4-.6.8-.7.4-.1.6.2.6.5-.1.4-.4.7-.8.7zm1-6.8c-.4.1-.8-.2-.7-.5.1-.4.4-.8.9-.9.4-.1.8.1.7.5 0 .4-.4.8-.9.9zm.8-7c-.5.1-.9-.1-.8-.6 0-.5.5-.9 1-1.1.5-.1.9.1.8.6 0 .5-.5 1-1 1.1zm.6-7.1c-.5.2-.9-.1-.9-.6s.5-1.1 1-1.3c.5-.2 1 .1.9.6 0 .6-.5 1.2-1 1.3zm3.4 33.2c0 .1-.2.3-.4.3s-.3-.1-.2-.2c0-.1.2-.3.4-.3.1 0 .2.1.2.2zm1.2-6.6c-.3 0-.4-.1-.4-.3 0-.2.3-.4.5-.4.3 0 .4.1.4.3 0 .2-.3.4-.5.4zm1.2-7.1c-.3.1-.6-.1-.5-.4 0-.3.4-.6.7-.6.3-.1.6.1.5.4 0 .2-.3.5-.7.6zm1-7.4c-.4.1-.7-.1-.7-.5s.4-.8.8-.9c.4-.1.7.1.7.5 0 .5-.4.8-.8.9zm.7-7.4c-.5.1-.9-.1-.8-.5 0-.4.4-.9.9-1.1.5-.2.9.1.8.5 0 .4-.4.9-.9 1.1zm.4-7.6c-.5.2-.9 0-.9-.5s.5-1 1-1.3c.5-.2 1 0 .9.5 0 .6-.5 1.1-1 1.3zm5.7 28.3c-.2 0-.4-.1-.3-.3 0-.2.2-.3.4-.4.2 0 .4.1.3.3 0 .2-.2.4-.4.4zm1.2-7.7c-.3.1-.5-.1-.5-.3 0-.2.3-.5.6-.6.3-.1.5.1.5.3 0 .3-.3.5-.6.6zm.9-7.9c-.4.1-.7-.1-.6-.4 0-.3.4-.7.7-.8.4-.1.7.1.7.4-.1.3-.4.7-.8.8zm.5-8c-.5.1-.8-.1-.8-.5s.4-.9.9-1c.5-.2.8 0 .8.5 0 .4-.4.8-.9 1zm8.4 13.7c-.3.1-.4-.1-.4-.3 0-.2.3-.4.5-.5.3-.1.5.1.4.3 0 .2-.2.5-.5.5zm.8-8.5c-.4.1-.6-.1-.6-.4 0-.3.3-.6.7-.7.4-.1.6.1.6.4 0 .3-.3.6-.7.7zm.4-8.7c-.4.2-.8 0-.8-.4s.4-.8.8-1c.4-.2.8 0 .8.4 0 .5-.4.9-.8 1zm9.7 14.5c-.2.1-.3 0-.3-.2s.2-.3.4-.4c.2 0 .3 0 .3.2-.1.2-.2.4-.4.4zm.6-9.2c-.3.1-.5 0-.5-.3 0-.2.3-.5.5-.6.3-.1.5 0 .5.3.1.2-.2.5-.5.6zM213.7 6c-.2.1-.4 0-.4-.2s.2-.4.4-.5c.2-.1.4 0 .4.2s-.1.4-.4.5z"/><path class="st0" d="M86.6 55.4c-.1 0-.3 0-.3.1s0 .2.1.2.3 0 .3-.1c.1-.1 0-.2-.1-.2zM82.5 54.8c-.1 0-.3 0-.3.1-.1.1 0 .2.2.2.1 0 .3 0 .3-.1s0-.2-.2-.2zM78.6 54.2c-.1 0-.3 0-.4.2-.1.1 0 .2.2.2.1 0 .3 0 .4-.1 0-.2-.1-.3-.2-.3zM74.7 53.7c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2.1 0 .3-.1.4-.2l-.2-.2zM70.8 53.3c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2s.3-.1.4-.2c0 0 0-.2-.2-.2zM67 53c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2s.3-.1.4-.2c0-.1 0-.2-.2-.2zM63.2 52.7c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2s.3-.1.4-.2c0-.1 0-.2-.2-.2zM59.4 52.5c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2s.3-.1.4-.2c.1-.1 0-.2-.2-.2zM55.7 52.3c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2s.3-.1.4-.2c0-.1 0-.2-.2-.2zM51.9 52.3c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2s.3-.1.4-.2c.1-.1 0-.2-.2-.2zM48.2 52.3c-.1 0-.3.1-.4.2 0 .1 0 .2.2.2s.3-.1.4-.2c0-.1-.1-.2-.2-.2zM44.4 52.4c-.1 0-.3.1-.3.2s0 .2.2.2c.1 0 .3-.1.3-.2s-.1-.2-.2-.2zM40.6 52.6c-.1 0-.3.1-.3.2s0 .2.2.2c.1 0 .3-.1.3-.2 0-.2-.1-.2-.2-.2zM36.7 52.9c-.1 0-.3.1-.3.2s0 .2.2.1c.1 0 .2-.1.3-.2 0-.1-.1-.1-.2-.1zM105.7 55.1c-.1 0-.3 0-.3.1s0 .2.2.2c.1 0 .3 0 .3-.1s-.1-.2-.2-.2zM101.1 54.3c-.2 0-.3 0-.4.2-.1.1 0 .2.2.2s.3 0 .4-.2c0-.1-.1-.2-.2-.2zM96.6 53.6c-.2 0-.3.1-.4.2-.1.1 0 .2.2.3.2 0 .3 0 .4-.2.1-.1 0-.3-.2-.3zM92.3 53c-.2 0-.4.1-.4.2-.1.1 0 .3.2.3s.4-.1.4-.2c.1-.2 0-.3-.2-.3zM88.1 52.4c-.2 0-.4.1-.5.2-.1.1 0 .3.2.3s.4-.1.5-.2c.1-.2 0-.3-.2-.3zM84 51.8c-.2 0-.4.1-.5.2-.1.1 0 .3.2.3s.4-.1.5-.2c.1-.1 0-.3-.2-.3zM80 51.3c-.2 0-.4.1-.5.2-.1.2 0 .3.2.3s.4-.1.5-.2c.1-.2 0-.3-.2-.3zM76.1 50.8c-.2 0-.4.1-.5.2-.1.2 0 .3.2.3s.4-.1.5-.2c.1-.1 0-.2-.2-.3zM72.2 50.4c-.2 0-.4.1-.5.2-.1.2 0 .3.2.3s.4-.1.5-.2c.1-.1 0-.3-.2-.3zM68.4 50.1c-.2 0-.4.1-.5.3-.1.2 0 .3.3.3.2 0 .4-.1.5-.3 0-.2-.1-.3-.3-.3zM64.6 49.8c-.2 0-.4.1-.5.3-.1.2 0 .3.3.3.2 0 .4-.1.5-.3 0-.2-.1-.3-.3-.3zM60.8 49.6c-.2 0-.4.1-.5.3-.1.2 0 .3.3.3.2 0 .4-.1.5-.3 0-.2-.1-.3-.3-.3zM57 49.4c-.2 0-.4.1-.5.3-.1.2 0 .3.3.3.2 0 .4-.1.5-.3 0-.2-.1-.3-.3-.3zM53.2 49.3c-.2 0-.4.1-.5.3-.1.2 0 .3.3.3.2 0 .4-.1.5-.3 0-.2-.1-.3-.3-.3zM49.4 49.3c-.2 0-.4.1-.5.3-.1.2 0 .3.2.3s.4-.1.5-.3c.1-.2 0-.3-.2-.3zM45.6 49.3c-.2 0-.4.1-.5.3-.1.2 0 .3.2.3s.4-.1.5-.3c.1-.1 0-.3-.2-.3zM41.8 49.5c-.2 0-.4.1-.5.3-.1.2.1.3.2.3.2 0 .4-.1.5-.3.1-.2 0-.3-.2-.3zM37.9 49.7c-.2 0-.4.1-.4.3-.1.1.1.3.2.2.2 0 .4-.1.4-.3.1-.1 0-.2-.2-.2zM33.9 50.1c-.2 0-.3.1-.4.3-.1.1 0 .2.2.2s.3-.1.4-.3c.1-.1 0-.2-.2-.2zM29.9 50.5c-.2 0-.3.1-.4.3 0 .1 0 .2.2.2s.3-.1.4-.3c.1-.1 0-.2-.2-.2zM117.3 52.9c-.2 0-.3.1-.4.2-.1.1 0 .2.2.2s.3-.1.4-.2c.1-.1 0-.2-.2-.2zM112.3 52.2c-.2 0-.4.1-.4.2-.1.1 0 .3.2.3s.4-.1.4-.2c0-.2-.1-.3-.2-.3zM107.4 51.5c-.2 0-.4.1-.5.2-.1.1 0 .3.2.3s.4-.1.5-.2c.1-.1 0-.3-.2-.3zM102.7 50.9c-.2 0-.4.1-.5.2-.1.2 0 .3.2.3s.4-.1.5-.2c.2-.1 0-.3-.2-.3zM98.2 50.3c-.2 0-.5.1-.5.3-.1.2 0 .3.3.4.2 0 .5-.1.5-.3.1-.3 0-.4-.3-.4zM93.9 49.7c-.2 0-.5.1-.6.3-.1.2 0 .3.3.4.2 0 .5-.1.6-.3 0-.2-.1-.4-.3-.4zM89.6 49.1c-.2 0-.5.1-.6.3-.1.2 0 .4.3.4.2 0 .5-.1.6-.3.1-.2 0-.3-.3-.4zM85.5 48.6c-.2 0-.5.1-.6.3-.1.2 0 .4.3.4.2 0 .5-.1.6-.3.1-.2 0-.4-.3-.4zM81.5 48.1c-.2 0-.5.1-.6.3-.1.2 0 .4.3.4.2 0 .5-.1.6-.3 0-.1-.1-.3-.3-.4zM77.5 47.7c-.3 0-.5.1-.6.3-.1.2 0 .4.3.4s.5-.1.6-.3c.1-.2-.1-.4-.3-.4zM73.6 47.3c-.3 0-.5.1-.6.3-.1.2 0 .4.3.4s.5-.1.6-.3c.1-.2-.1-.3-.3-.4zM69.7 47c-.3 0-.5.1-.6.3-.1.2.1.4.3.4.3 0 .5-.1.6-.3.1-.2 0-.4-.3-.4zM65.9 46.7c-.3 0-.5.1-.6.4-.1.2.1.4.3.4.3 0 .6-.1.6-.3.1-.3-.1-.5-.3-.5zM62.1 46.5c-.3 0-.5.1-.6.4-.1.2.1.4.3.4.3 0 .5-.1.6-.4.1-.2-.1-.4-.3-.4zM58.3 46.3c-.3 0-.5.2-.6.4-.1.2.1.4.3.4.3 0 .5-.2.6-.4.1-.2-.1-.4-.3-.4zM54.5 46.2c-.3 0-.5.2-.6.4-.1.2.1.4.3.4.3 0 .5-.2.6-.4.1-.2-.1-.4-.3-.4zM50.7 46.1c-.3 0-.5.2-.6.4-.1.2.1.4.3.4.3 0 .5-.2.6-.4.1-.2-.1-.4-.3-.4zM46.8 46.2c-.2 0-.5.2-.6.4-.1.2.1.4.3.4.2 0 .5-.2.6-.4.1-.3 0-.4-.3-.4zM43 46.3c-.2 0-.5.2-.6.4-.1.2.1.3.3.3.2 0 .5-.2.6-.4.1-.2-.1-.3-.3-.3zM39.1 46.5c-.2 0-.5.2-.5.4-.1.2.1.3.3.3.2 0 .5-.2.5-.4s-.1-.4-.3-.3zM35.1 46.7c-.2 0-.5.2-.5.4-.1.2.1.3.3.3.2 0 .5-.2.5-.4.1-.1-.1-.3-.3-.3zM31.1 47.1c-.2 0-.4.2-.5.4-.1.2.1.3.3.3.2 0 .4-.2.5-.3 0-.3-.1-.4-.3-.4zM27 47.6c-.2 0-.4.2-.4.3-.1.2.1.3.3.2.2 0 .4-.2.4-.3 0-.1-.1-.2-.3-.2zM22.8 48.2c-.2 0-.4.2-.4.3 0 .1.1.2.2.2.2 0 .4-.2.4-.3.1-.1 0-.2-.2-.2zM142.5 51.1c-.1 0-.2.1-.3.1 0 .1 0 .2.1.2s.2-.1.3-.1c.1-.1 0-.2-.1-.2zM136.1 50.5c-.2 0-.3.1-.4.2 0 .1 0 .2.2.2s.3-.1.4-.2c.1-.1 0-.2-.2-.2zM130.1 49.9c-.2 0-.4.1-.4.2-.1.1 0 .3.2.3s.4-.1.4-.2c.1-.1 0-.2-.2-.3zM124.4 49.4c-.2 0-.4.1-.5.3-.1.2.1.3.3.3.2 0 .4-.1.5-.3.1-.1-.1-.3-.3-.3zM119.1 48.8c-.2 0-.5.1-.5.3-.1.2.1.3.3.4.2 0 .5-.1.5-.3 0-.2-.1-.4-.3-.4zM113.9 48.3c-.2 0-.5.1-.6.3-.1.2.1.4.3.4.2 0 .5-.1.6-.3.1-.2 0-.4-.3-.4zM109 47.7c-.3 0-.5.1-.6.3-.1.2.1.4.3.4.3 0 .5-.1.6-.3.1-.2 0-.4-.3-.4zM104.3 47.2c-.3 0-.6.1-.6.3-.1.2.1.4.3.4.3 0 .6-.1.7-.3 0-.2-.1-.4-.4-.4zM99.8 46.7c-.3 0-.6.1-.7.4-.1.2.1.4.3.5.3 0 .6-.1.7-.4.1-.3 0-.5-.3-.5zM95.4 46.2c-.3 0-.6.1-.7.4-.1.2 0 .4.3.4s.6-.1.7-.4c.1-.2 0-.4-.3-.4zM91.1 45.7c-.3 0-.6.1-.7.4-.1.2.1.5.4.5.3 0 .6-.1.7-.4.1-.3-.1-.5-.4-.5zM86.9 45.2c-.3 0-.6.1-.7.4-.1.2.1.5.4.5.3 0 .6-.1.7-.4.1-.2-.1-.4-.4-.5zM82.9 44.8c-.3 0-.6.2-.7.4-.1.2.1.5.4.5.3 0 .6-.1.7-.4 0-.2-.1-.5-.4-.5zM78.9 44.4c-.3 0-.6.2-.7.4-.1.3.1.5.4.5.3 0 .6-.2.8-.4-.1-.2-.2-.5-.5-.5zM74.9 44.1c-.3 0-.6.2-.7.4-.1.3.1.5.4.5.3 0 .6-.2.8-.4 0-.3-.2-.5-.5-.5zM71 43.7c-.3 0-.7.2-.8.4-.1.3.1.5.4.5.3 0 .7-.2.8-.4.1-.2-.1-.4-.4-.5zM67.2 43.5c-.3 0-.6.2-.8.4-.1.3.1.5.4.5.3 0 .7-.2.8-.4.1-.3-.1-.5-.4-.5zM63.3 43.3c-.3 0-.6.2-.7.4-.1.3.1.5.4.5.3 0 .6-.2.7-.4.1-.3 0-.5-.4-.5zM59.5 43.1c-.3 0-.6.2-.7.5-.1.3.1.5.4.5.3 0 .6-.2.7-.4.1-.4-.1-.6-.4-.6zM55.7 42.9c-.3 0-.6.2-.7.5-.1.3.1.5.4.5.3 0 .6-.2.7-.5.1-.2-.1-.5-.4-.5zM51.9 42.9c-.3 0-.6.2-.7.5-.1.3.1.5.4.5.3 0 .6-.2.7-.5.1-.3-.1-.5-.4-.5zM48.1 42.9c-.3 0-.6.2-.7.5-.1.2.1.4.4.4.3 0 .6-.2.7-.5 0-.2-.1-.4-.4-.4zM44.2 42.9c-.3 0-.6.2-.7.5-.1.2.1.4.4.4.3 0 .6-.2.7-.5.1-.2-.1-.4-.4-.4zM40.7 43.5c.1-.2-.1-.4-.4-.4-.3 0-.6.2-.7.5-.1.2.1.4.4.4.3-.1.6-.3.7-.5zM36.7 43.7c.1-.2-.1-.4-.3-.4-.3 0-.6.2-.6.5-.1.2.1.4.3.4.2-.1.5-.3.6-.5zM32.3 43.6c-.3 0-.5.2-.6.4-.1.2.1.4.3.4.3 0 .5-.2.6-.4.1-.3 0-.4-.3-.4zM28.2 44c-.3 0-.5.2-.6.4-.1.2.1.4.3.3.3 0 .5-.2.6-.4.1-.2 0-.3-.3-.3zM24 44.5c-.2 0-.5.2-.5.4-.1.2.1.3.3.3.2 0 .5-.2.5-.4.1-.2 0-.3-.3-.3zM19.7 45.1c-.2 0-.4.2-.5.4-.1.2.1.3.3.3.2 0 .4-.2.5-.4.1-.2-.1-.3-.3-.3zM151.4 46c-.2 0-.3.1-.4.2 0 .1.1.2.2.2.2 0 .3-.1.4-.2 0-.1-.1-.2-.2-.2zM144.4 45.8c-.2 0-.4.1-.4.3-.1.2.1.3.3.3.2 0 .4-.1.5-.3-.1-.2-.2-.3-.4-.3zM137.9 45.5c-.2 0-.5.1-.5.3-.1.2.1.3.3.3.2 0 .5-.1.5-.3.1-.1 0-.3-.3-.3zM131.9 45.2c-.3 0-.5.1-.6.3-.1.2.1.4.3.4.3 0 .5-.1.6-.3.1-.2-.1-.4-.3-.4zM126.1 44.8c-.3 0-.6.2-.6.4-.1.2.1.4.4.4.3 0 .6-.1.6-.4.1-.1-.1-.3-.4-.4zM120.7 44.5c-.3 0-.6.2-.7.4-.1.2.1.4.4.5.3 0 .6-.2.7-.4 0-.3-.1-.5-.4-.5zM115.5 44.1c-.3 0-.6.2-.7.4-.1.3.1.5.4.5.3 0 .6-.2.7-.4.1-.3-.1-.5-.4-.5zM110.6 43.7c-.3 0-.6.2-.7.4-.1.3.1.5.4.5.3 0 .7-.2.7-.4.1-.3-.1-.5-.4-.5zM105.8 43.3c-.3 0-.7.2-.8.4-.1.3.1.5.4.5.3 0 .7-.2.8-.4.1-.3-.1-.5-.4-.5zM101.2 42.9c-.3 0-.7.2-.8.5-.1.3.1.5.4.6.3 0 .7-.2.8-.4.1-.5 0-.7-.4-.7zM96.8 42.5c-.3 0-.7.2-.8.5-.1.3.1.5.4.6.3 0 .7-.2.8-.5.1-.4-.1-.6-.4-.6zM92.5 42.1c-.3 0-.7.2-.8.5-.1.3.1.6.4.6.3 0 .7-.2.8-.5.1-.3-.1-.6-.4-.6zM88.3 41.7c-.3 0-.7.2-.8.5-.1.3.1.6.4.6.3 0 .7-.2.8-.5.1-.3-.1-.6-.4-.6zM84.2 41.3c-.4 0-.7.2-.8.5-.1.3.1.6.4.6.4 0 .7-.2.8-.5.1-.3 0-.6-.4-.6zM80.2 41c-.3 0-.7.2-.8.5-.1.3.1.6.4.6.3 0 .7-.2.8-.5.1-.3-.1-.6-.4-.6zM76.2 40.7c-.4 0-.7.2-.9.5-.1.3.1.6.4.6.4 0 .7-.2.9-.5.2-.3 0-.6-.4-.6zM72.3 40.4c-.4 0-.7.2-.9.5-.1.3.1.6.4.6.4 0 .7-.2.9-.5.2-.3 0-.6-.4-.6zM68.5 40.1c-.4 0-.7.2-.9.5-.1.3.1.6.4.6.4 0 .7-.2.9-.5.1-.3-.1-.6-.4-.6zM64.6 39.9c-.4 0-.7.2-.9.5-.1.3.1.6.4.6.4 0 .7-.2.9-.5.2-.3 0-.6-.4-.6zM60.8 39.7c-.4 0-.7.2-.8.5-.1.3.1.6.4.6.4 0 .7-.2.8-.5.1-.3 0-.6-.4-.6zM57 39.6c-.3 0-.7.2-.8.5-.1.3.1.6.4.6.3 0 .7-.2.8-.5.1-.3-.1-.6-.4-.6zM53.2 39.5c-.3 0-.7.2-.8.5-.1.3.1.5.4.6.3 0 .7-.2.8-.5.1-.3-.1-.6-.4-.6zM49.3 39.5c-.3 0-.7.2-.8.5-.1.3.1.5.4.5.3 0 .7-.2.8-.5.1-.3-.1-.5-.4-.5zM45.8 40c.1-.3-.1-.5-.4-.5-.3 0-.7.2-.8.5-.1.3.1.5.4.5.4 0 .7-.2.8-.5zM41.9 40.1c.1-.3-.1-.5-.4-.5-.3 0-.7.2-.8.5-.1.3.1.5.4.5.4 0 .7-.2.8-.5zM38 40.2c.1-.3-.1-.5-.4-.5-.3 0-.7.3-.7.5-.1.3.1.5.4.5.2 0 .6-.2.7-.5zM33.9 40.4c.1-.3-.1-.5-.4-.5-.3 0-.6.3-.7.5-.1.3.1.5.4.4.3.1.6-.1.7-.4zM29.8 40.7c.1-.3-.1-.4-.4-.4-.3 0-.6.3-.7.5-.1.3.1.4.4.4.3 0 .6-.2.7-.5zM25.2 40.8c-.3 0-.5.2-.6.5-.1.2.1.4.3.4.3 0 .5-.2.6-.5.1-.3 0-.5-.3-.4zM20.9 41.3c-.2 0-.5.2-.6.4-.1.2.1.4.3.3.2 0 .5-.2.5-.4.2-.2.1-.3-.2-.3zM16.5 41.9c-.2 0-.4.2-.5.4-.1.2.1.3.3.3.2 0 .4-.2.5-.4 0-.2-.1-.3-.3-.3zM12 42.7c-.2 0-.4.2-.4.4-.1.2.1.3.2.2.2 0 .4-.2.4-.4.1-.1 0-.2-.2-.2zM168.8 39.5c-.2 0-.3.1-.4.3 0 .1.1.2.2.2.2 0 .3-.1.4-.3.1-.1 0-.2-.2-.2zM160.7 39.8c-.2 0-.4.2-.4.3 0 .2.1.3.3.3.2 0 .4-.2.5-.3-.1-.1-.2-.3-.4-.3zM153.1 40.1c-.2 0-.5.2-.5.4-.1.2.1.4.3.3.2 0 .5-.2.5-.4.1-.2 0-.3-.3-.3zM146.1 40.2c-.3 0-.5.2-.6.4-.1.2.1.4.4.4.3 0 .6-.2.6-.4.1-.2-.1-.4-.4-.4zM139.6 40.2c-.3 0-.6.2-.7.5-.1.2.1.4.4.5.3 0 .6-.2.7-.5.1-.3-.1-.5-.4-.5zM133.5 40.2c-.3 0-.6.2-.7.5-.1.3.1.5.4.5.3 0 .6-.2.7-.5.1-.3-.1-.5-.4-.5zM127.7 40c-.3 0-.7.2-.8.5-.1.3.1.5.5.5.3 0 .7-.2.8-.5 0-.2-.2-.5-.5-.5zM122.2 39.9c-.3 0-.7.2-.8.5-.1.3.1.5.5.6.3 0 .7-.2.8-.5.1-.4-.2-.6-.5-.6zM117.5 40.3c.1-.3-.1-.6-.5-.6s-.7.2-.8.5c-.1.3.1.6.5.6.3 0 .7-.2.8-.5zM112 39.4c-.4 0-.7.2-.9.5-.1.3.1.6.5.6s.8-.2.9-.5c.1-.3-.1-.6-.5-.6zM107.2 39.2c-.4 0-.8.2-.9.6-.1.3.1.6.5.6s.8-.2.9-.6c.1-.3-.1-.6-.5-.6zM102.6 38.9c-.4 0-.8.2-.9.6-.1.3.1.6.5.6s.8-.2.9-.6c.1-.3-.1-.6-.5-.6zM98.2 38.6c-.4 0-.8.2-.9.6-.1.3.1.6.5.7.4 0 .8-.2.9-.6.1-.4-.2-.7-.5-.7zM93.8 38.3c-.4 0-.8.2-.9.6-.1.3.1.6.5.7.4 0 .8-.2.9-.6.2-.4-.1-.7-.5-.7zM89.6 38c-.4 0-.8.2-.9.6-.1.3.1.7.5.7s.8-.2.9-.6c.1-.4-.1-.7-.5-.7zM85.5 37.7c-.4 0-.8.2-.9.6-.1.3.1.7.5.7s.8-.2.9-.6c.1-.4-.1-.7-.5-.7zM81.5 37.4c-.4 0-.8.2-.9.6-.1.4.1.7.5.7s.8-.2.9-.6c.1-.4-.1-.7-.5-.7zM77.5 37.2c-.4 0-.8.2-.9.6-.1.3.1.6.5.7.4 0 .8-.2.9-.6.1-.4-.1-.7-.5-.7zM73.6 36.9c-.4 0-.8.2-.9.6-.1.3.1.7.5.7s.8-.2.9-.6c.1-.4-.1-.7-.5-.7zM69.7 36.7c-.4 0-.8.2-.9.6-.1.3.1.6.5.7.4 0 .8-.2.9-.6.1-.4-.1-.7-.5-.7zM65.9 36.5c-.4 0-.8.3-.9.6-.1.3.1.6.5.7.4 0 .8-.2.9-.6.1-.4-.1-.7-.5-.7zM62.1 36.3c-.4 0-.8.3-.9.6-.1.3.1.6.5.7.4 0 .8-.2.9-.6.1-.4-.2-.7-.5-.7zM58.2 36.1c-.4 0-.8.3-.9.6-.1.3.1.6.5.6s.8-.3.9-.6c.1-.2-.1-.5-.5-.6zM54.4 36.1c-.4 0-.8.3-.9.6-.1.3.1.6.5.6s.8-.3.9-.6c.1-.4-.1-.6-.5-.6zM50.6 36c-.4 0-.8.3-.9.6-.1.3.1.6.5.6s.8-.3.9-.6c.1-.3-.1-.6-.5-.6zM46.7 36c-.4 0-.8.3-.9.6-.1.3.1.6.5.6s.8-.3.9-.6c.1-.3-.1-.6-.5-.6zM43.2 36.6c.1-.3-.1-.6-.5-.6s-.8.3-.9.6c-.1.3.1.6.5.6s.8-.3.9-.6zM39.3 36.7c.1-.3-.1-.6-.4-.6-.4 0-.7.3-.9.6-.1.3.1.6.4.6.4 0 .8-.3.9-.6zM35.2 36.8c.1-.3-.1-.5-.4-.5-.3 0-.7.3-.8.6-.1.3.1.5.4.5.4 0 .7-.2.8-.6zM31.1 37.1c.1-.3-.1-.5-.4-.5-.3 0-.7.3-.8.6-.1.3.1.5.4.5.4-.1.7-.3.8-.6zM26.9 37.4c.1-.3-.1-.5-.4-.5-.3 0-.7.3-.8.6-.1.3.1.5.4.5.4-.1.7-.3.8-.6zM22.6 37.8c.1-.3-.1-.5-.4-.4-.3 0-.6.3-.7.6-.1.3.1.5.4.4.3-.1.7-.4.7-.6zM17.8 37.9c-.2 0-.5.2-.6.5-.1.2.1.4.3.3.2 0 .5-.2.6-.4.1-.3 0-.4-.3-.4zM13.3 38.6c-.2 0-.5.2-.5.4-.1.2.1.3.3.3.2 0 .5-.2.5-.4s-.1-.4-.3-.3zM8.6 39.3c-.2 0-.4.2-.5.4 0 .2.1.3.3.3.2 0 .4-.2.5-.4 0-.2-.1-.3-.3-.3zM179.4 31.2c-.2 0-.4.2-.4.4s.1.3.3.3c.2 0 .4-.2.5-.4-.1-.2-.2-.3-.4-.3zM170.4 32.3c-.3 0-.5.2-.5.4s.1.4.4.3c.3 0 .5-.2.6-.4 0-.2-.2-.3-.5-.3zM162.2 33.2c-.3 0-.6.3-.6.5s.1.4.4.4c.3 0 .6-.3.6-.5.1-.3-.1-.5-.4-.4zM154.7 33.8c-.3 0-.6.3-.7.6-.1.3.1.5.5.5.3 0 .6-.3.7-.6 0-.3-.2-.5-.5-.5zM147.6 34.3c-.4 0-.7.3-.8.6-.1.3.2.5.5.5.4 0 .7-.3.8-.6.1-.3-.1-.5-.5-.5zM141.1 34.6c-.4 0-.7.3-.8.6-.1.3.2.6.5.6.4 0 .7-.3.8-.6.1-.3-.2-.6-.5-.6zM134.9 34.9c-.4 0-.8.3-.9.6-.1.3.2.6.5.6.4 0 .8-.3.9-.6.1-.4-.1-.6-.5-.6zM129.1 35c-.4 0-.8.3-.9.7-.1.3.1.6.5.6s.8-.3.9-.6c.1-.4-.1-.7-.5-.7zM124.2 35.7c.1-.4-.2-.7-.6-.7-.4 0-.8.3-.9.7-.1.4.1.7.6.7.3 0 .8-.3.9-.7zM118.9 35.7c.1-.4-.2-.7-.6-.7-.4 0-.9.3-1 .7-.1.4.1.7.6.7s.9-.3 1-.7zM113.9 35.7c.1-.4-.1-.7-.6-.7-.4 0-.9.3-1 .7-.1.4.1.7.6.7s.9-.3 1-.7zM109.1 35.6c.1-.4-.1-.7-.6-.7-.4 0-.9.3-1 .7-.1.4.1.7.6.7s.9-.3 1-.7zM104.5 35.5c.1-.4-.1-.7-.6-.7-.4 0-.9.3-1 .7-.1.4.1.7.6.7.4 0 .9-.3 1-.7zM100 35.3c.1-.4-.1-.7-.6-.7-.4 0-.9.3-1 .7-.1.3.2.7.6.7.5 0 .9-.3 1-.7zM94.1 35.1c-.1.4.1.7.6.7.4 0 .9-.3 1-.7.1-.4-.1-.7-.6-.7-.4 0-.9.3-1 .7zM90.9 34.2c-.4 0-.9.3-1 .7-.1.4.1.7.6.8.4 0 .9-.3 1-.7.1-.5-.2-.8-.6-.8zM86.8 34c-.4 0-.9.3-1 .7-.1.4.1.7.5.8.4 0 .9-.3 1-.7.2-.5-.1-.8-.5-.8zM82.7 33.7c-.4 0-.9.3-1 .7-.1.4.1.7.5.8.4 0 .9-.3 1-.7.2-.4 0-.7-.5-.8zM78.3 35c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.8-.4 0-.9.3-1 .7-.2.4 0 .7.5.8zM74.4 34.7c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.8-.4 0-.9.3-1 .7-.2.5 0 .8.5.8zM70.5 34.5c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.8-.4 0-.9.3-1 .7-.2.5.1.8.5.8zM66.6 34.4c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.1.3.1.6.5.7zM62.8 34.2c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.1.3.1.7.5.7zM59 34c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.2.4.1.7.5.7zM55.2 33.9c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.2.4.1.7.5.7zM51.3 33.8c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.1.4.1.7.5.7zM47.5 33.8c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.1.4.1.7.5.7zM44.1 32.4c-.4 0-.9.3-1 .7-.1.4.1.7.5.7s.8-.3 1-.7c.1-.4-.1-.7-.5-.7zM39.7 33.8c.4 0 .8-.3.9-.7.1-.4-.1-.6-.5-.6s-.8.3-.9.7c-.1.3.1.6.5.6zM35.7 33.9c.4 0 .8-.3.9-.7.1-.4-.1-.6-.5-.6s-.8.3-.9.7c-.1.3.1.6.5.6zM32.5 33.4c.1-.3-.1-.6-.5-.6s-.8.3-.9.7c-.1.3.1.6.5.6.4-.1.8-.4.9-.7zM28.3 33.6c.1-.3-.1-.6-.5-.6s-.8.3-.9.6c-.1.3.1.6.5.6s.8-.3.9-.6zM24.1 33.9c.1-.3-.1-.6-.4-.5-.4 0-.7.3-.9.6-.1.3.1.6.4.5.4 0 .7-.3.9-.6zM19.7 34.3c.1-.3-.1-.5-.4-.5-.3 0-.7.3-.8.6-.1.3.1.5.4.5.3 0 .7-.3.8-.6zM14.7 34.4c-.3 0-.6.3-.6.5-.1.2.1.4.3.4.3 0 .5-.3.6-.5.1-.3-.1-.4-.3-.4zM10 35c-.3 0-.5.2-.6.5-.1.2.1.4.3.3.3 0 .5-.2.6-.5.1-.2 0-.3-.3-.3zM5.2 36c-.1 0-.3.1-.3.3 0 .1 0 .2.2.2.1 0 .3-.1.3-.3 0-.1-.1-.2-.2-.2zM201.2 18.8c-.2.1-.4.2-.4.4s.1.3.3.2c.2 0 .4-.2.4-.4.1-.2-.1-.3-.3-.2zM190.4 21.2c-.3.1-.5.3-.5.5s.2.3.4.3c.3-.1.5-.3.5-.5.1-.2-.1-.3-.4-.3zM180.6 23.3c-.3.1-.6.3-.6.6 0 .2.2.4.5.3.3-.1.6-.3.6-.6 0-.2-.2-.4-.5-.3zM171.7 24.9c-.3.1-.6.3-.7.6 0 .3.2.5.5.4.3-.1.7-.3.7-.6.1-.3-.2-.5-.5-.4zM163.5 26.3c-.4.1-.7.4-.8.7-.1.3.2.5.6.5.4-.1.7-.4.8-.7 0-.4-.2-.6-.6-.5zM155.9 27.3c-.4.1-.7.4-.8.7-.1.3.2.6.6.5.4-.1.8-.4.8-.7.1-.3-.2-.5-.6-.5zM148.9 28.2c-.4.1-.8.4-.9.8-.1.4.2.6.6.6.4 0 .8-.4.9-.8.1-.4-.2-.7-.6-.6zM142.4 28.9c-.4 0-.8.4-.9.8-.1.4.2.7.6.6.4 0 .9-.4.9-.8.1-.4-.2-.7-.6-.6zM136.2 29.4c-.4 0-.9.4-1 .8-.1.4.2.7.6.7.4 0 .9-.4 1-.8.1-.4-.2-.7-.6-.7zM130.4 29.8c-.5 0-.9.4-1 .8-.1.4.2.7.6.7.5 0 .9-.4 1-.8.1-.4-.2-.7-.6-.7zM124.9 30.1c-.5 0-.9.4-1 .8-.1.4.2.7.6.7.5 0 .9-.4 1-.8.1-.4-.2-.7-.6-.7zM119.6 30.3c-.5 0-.9.4-1 .8-.1.4.2.8.6.7.5 0 .9-.4 1.1-.8.1-.4-.2-.7-.7-.7zM114.2 32c.5 0 1-.4 1.1-.8.1-.4-.2-.8-.6-.8-.5 0-.9.4-1.1.8-.1.5.1.8.6.8zM110.5 31.3c.1-.4-.2-.8-.6-.8-.5 0-.9.4-1.1.8-.1.4.2.8.6.8.5 0 .9-.4 1.1-.8zM105.8 31.3c.1-.4-.2-.8-.6-.8-.5 0-1 .4-1.1.8-.1.4.2.8.6.8.5 0 1-.4 1.1-.8zM101.4 31.3c.1-.4-.2-.8-.6-.8-.5 0-1 .3-1.1.8-.1.4.1.8.6.8.4-.1.9-.4 1.1-.8zM97 31.2c.1-.4-.1-.8-.6-.8s-1 .3-1.1.8c-.1.4.1.8.6.8s1-.4 1.1-.8zM91.7 31.9c.5 0 1-.3 1.1-.8.1-.4-.1-.8-.6-.8s-1 .3-1.1.8c-.2.4.1.7.6.8zM87.5 31.7c.5 0 1-.3 1.1-.8.1-.4-.1-.8-.6-.8s-1 .3-1.1.8c-.1.4.1.8.6.8zM83.5 31.6c.5 0 1-.3 1.1-.8.1-.4-.1-.8-.6-.8s-1 .3-1.1.8c-.2.4.1.8.6.8zM80.6 30.7c.1-.4-.1-.8-.6-.8s-1 .3-1.1.8c-.1.4.1.8.6.8.5-.1 1-.4 1.1-.8zM76.7 30.5c.1-.4-.1-.8-.6-.8s-1 .3-1.1.7c-.1.4.1.8.6.8.4.1.9-.3 1.1-.7zM72.8 30.3c.1-.4-.1-.8-.6-.8s-1 .3-1.1.7c-.2.4.1.8.6.8.5.1 1-.2 1.1-.7zM69 30.2c.1-.4-.1-.8-.6-.8s-1 .3-1.1.7c-.2.4.1.8.6.8.4 0 .9-.3 1.1-.7zM65.2 30c.2-.4-.1-.8-.6-.8s-1 .3-1.1.7c-.2.4.1.8.6.8.4.1.9-.3 1.1-.7zM61.3 29.9c.2-.4-.1-.8-.6-.8s-1 .3-1.1.7c-.2.4.1.8.6.8s1-.3 1.1-.7zM57.5 29.8c.2-.4-.1-.8-.5-.8-.5 0-.9.3-1.1.7-.2.4.1.8.5.8.5 0 1-.3 1.1-.7zM53.7 29.7c.2-.4-.1-.8-.5-.8-.5 0-.9.3-1.1.7-.2.4.1.8.5.8.5 0 .9-.3 1.1-.7zM49.8 29.6c.1-.4-.1-.7-.5-.7s-.9.3-1.1.7c-.1.4.1.7.5.7.5 0 1-.3 1.1-.7zM44.9 30.3c.4 0 .9-.3 1.1-.7.1-.4-.1-.7-.5-.7s-.9.3-1.1.7c-.2.3 0 .7.5.7zM42 29.5c.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.1.4.1.7.5.7.4.1.9-.3 1-.7zM38 29.6c.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.1.4.1.7.5.7s.9-.3 1-.7zM32.9 30.4c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1 .7c-.1.4.1.7.5.7zM28.8 30.5c.4 0 .8-.3 1-.7.1-.4-.1-.6-.5-.6s-.9.3-1 .7c-.1.4.1.6.5.6zM25.5 30c.1-.4-.1-.6-.5-.6s-.8.3-1 .7c-.1.4.1.6.5.6.5 0 .9-.3 1-.7zM21.1 30.3c.1-.3-.1-.6-.5-.6s-.8.3-.9.7c-.1.3.1.6.5.6s.8-.3.9-.7zM16.6 30.7c.1-.3-.1-.6-.4-.5-.4 0-.8.3-.9.7-.1.3.1.6.5.5.3-.1.7-.4.8-.7zM11.9 31.2c.1-.3-.1-.5-.4-.5-.3 0-.7.3-.8.6-.1.3.1.5.4.4.4 0 .7-.3.8-.5zM6.8 31.5c-.3 0-.5.3-.6.5-.1.2.1.4.3.4.3 0 .5-.3.6-.5.1-.3 0-.4-.3-.4zM1.9 32.4c-.2 0-.4.2-.4.4-.1.2 0 .3.2.2.2 0 .4-.2.4-.4.1-.1 0-.3-.2-.2zM213.7 5.3c-.2.1-.4.3-.4.5s.2.3.4.2c.2-.1.4-.3.4-.5s-.1-.2-.4-.2zM201.9 9.2c-.3.1-.5.4-.5.6 0 .2.2.4.5.3.3-.1.5-.4.6-.6-.1-.3-.3-.4-.6-.3zM191.2 12.4c-.4.1-.6.4-.7.7 0 .3.2.5.6.4.4-.1.7-.4.7-.7 0-.3-.3-.5-.6-.4zM181.5 15.1c-.4.1-.7.5-.7.8 0 .3.3.5.6.4.4-.1.7-.5.8-.8 0-.3-.3-.5-.7-.4zM172.6 17.3c-.4.1-.8.5-.8.9s.3.6.7.5c.4-.1.8-.5.8-.9.1-.4-.2-.6-.7-.5zM164.5 19.1c-.4.1-.8.5-.9.9 0 .4.3.6.7.5.4-.1.8-.5.9-.9.1-.3-.2-.6-.7-.5zM157 20.7c-.5.1-.9.5-.9.9-.1.4.3.7.7.6.5-.1.9-.5.9-.9.1-.5-.2-.7-.7-.6zM150 21.9c-.5.1-.9.5-1 .9-.1.4.3.7.7.6.5-.1.9-.5 1-.9.1-.4-.2-.7-.7-.6zM143.5 23c-.5.1-.9.5-1 .9-.1.4.2.8.7.7.5-.1.9-.5 1-.9.1-.5-.2-.8-.7-.7zM138.1 24.5c.1-.5-.2-.8-.7-.7-.5.1-1 .5-1 .9-.1.5.2.8.7.7.4 0 .9-.4 1-.9zM131.5 24.5c-.5.1-1 .5-1.1.9-.1.5.2.8.7.7.5 0 1-.5 1.1-.9.2-.4-.2-.8-.7-.7zM126.1 25c-.5.1-1 .5-1.1.9-.1.5.2.8.7.8.5 0 1-.5 1.1-.9.1-.5-.2-.8-.7-.8zM120.8 25.4c-.5 0-1 .5-1.1.9-.1.5.2.8.7.8.5 0 1-.5 1.1-.9.2-.4-.2-.8-.7-.8zM115.8 25.8c-.5 0-1 .4-1.1.9-.1.5.2.8.7.8.5 0 1-.4 1.2-.9.1-.5-.3-.9-.8-.8zM110.6 27.7c.5 0 1-.4 1.2-.9.1-.5-.2-.9-.7-.8-.5 0-1 .4-1.1.9-.2.5.1.9.6.8zM105.9 27.9c.5 0 1-.4 1.2-.9.1-.5-.2-.9-.7-.8-.5 0-1 .4-1.2.9-.1.4.2.8.7.8zM101.4 28c.5 0 1-.4 1.2-.9.1-.5-.2-.9-.7-.9-.5 0-1 .4-1.2.9-.1.5.2.9.7.9zM97.1 28c.5 0 1-.4 1.2-.9.1-.5-.2-.9-.7-.9-.5 0-1 .4-1.2.9-.1.5.2.9.7.9zM94 27.2c.1-.5-.1-.9-.7-.9-.5 0-1 .4-1.2.9-.1.5.1.9.6.9.7-.1 1.2-.5 1.3-.9zM89.9 27.1c.1-.5-.1-.9-.6-.9s-1 .4-1.2.8c-.1.5.1.9.6.9.5.1 1.1-.3 1.2-.8zM85.9 27.1c.2-.5-.1-.9-.6-.9s-1 .4-1.2.8c-.2.5.1.9.6.9s1-.4 1.2-.8zM81.9 27c.2-.5-.1-.9-.6-.9s-1 .4-1.2.8c-.2.5.1.9.6.9s1-.3 1.2-.8zM78 26.9c.2-.5-.1-.9-.6-.9s-1 .4-1.2.8c-.2.5.1.9.6.9s1-.3 1.2-.8zM74.1 26.8c.2-.5-.1-.9-.6-.9s-1 .3-1.2.8c-.2.5.1.9.6.9s1.1-.4 1.2-.8zM70.3 26.6c.2-.5-.1-.8-.6-.9-.5 0-1 .3-1.2.8-.2.5.1.8.6.9.5.1 1-.3 1.2-.8zM66.5 26.5c.2-.5-.1-.8-.6-.8s-1 .3-1.2.8c-.2.5.1.8.6.8s1-.3 1.2-.8zM62.7 26.4c.2-.4-.1-.8-.6-.8s-1 .3-1.2.8c-.2.4.1.8.6.8s1-.4 1.2-.8zM58.9 26.3c.2-.4-.1-.8-.6-.8s-1 .3-1.2.8c-.1.4.1.7.6.7.5.1 1-.3 1.2-.7zM55 26.2c.2-.4-.1-.8-.6-.8s-1 .3-1.2.8c-.2.4.1.8.6.8.6-.1 1.1-.4 1.2-.8zM51.2 26.1c.2-.4-.1-.8-.6-.8s-1 .3-1.2.8c-.2.4.1.8.6.8.5-.1 1-.4 1.2-.8zM47.3 26c.2-.4-.1-.8-.5-.8-.5 0-1 .3-1.1.8-.2.4.1.8.5.8.5 0 1-.4 1.1-.8zM43.4 26c.2-.4-.1-.8-.5-.8-.5 0-1 .3-1.1.8-.2.4.1.8.5.8.5-.1 1-.4 1.1-.8zM39.4 26c.2-.4-.1-.7-.5-.7-.5 0-1 .3-1.1.7-.2.4.1.7.5.7.5 0 1-.3 1.1-.7zM35.4 26c.2-.4-.1-.7-.5-.7s-.9.3-1.1.7c-.2.4.1.7.5.7.5 0 .9-.3 1.1-.7zM31.3 26.1c.2-.4-.1-.7-.5-.7s-.9.3-1.1.7c-.2.4.1.7.5.7s.9-.3 1.1-.7zM26 26.9c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.7s-.9.3-1.1.7c-.1.5.2.8.6.7zM21.7 27.1c.4 0 .9-.3 1-.7.1-.4-.1-.7-.5-.6-.4 0-.9.3-1 .7-.2.4.1.6.5.6zM17.8 26.1c-.4 0-.9.3-1 .7-.1.4.1.6.5.6s.8-.3 1-.7c.1-.4-.1-.7-.5-.6zM13.2 26.4c-.4 0-.8.3-1 .7-.1.3.1.6.5.6s.8-.3.9-.7c.2-.3 0-.6-.4-.6zM8.8 27.6c.1-.3 0-.5-.3-.4-.3 0-.6.3-.7.5-.1.3 0 .5.3.4.3 0 .6-.2.7-.5zM3.7 27.8c-.3 0-.5.2-.6.5-.1.2 0 .4.3.4.2 0 .5-.2.6-.5.1-.2-.1-.4-.3-.4zM202 .8c.4-.1.6-.5.7-.8h-1.3c-.1.1-.2.3-.2.4 0 .4.4.5.8.4zM191.5 3.5c-.4.2-.8.6-.8 1s.3.6.8.4c.4-.2.8-.6.8-1s-.4-.6-.8-.4zM182 6.8c-.5.2-.8.6-.9 1 0 .4.3.6.8.5.5-.2.8-.6.9-1 0-.5-.4-.7-.8-.5zM173.3 9.6c-.5.2-.9.6-.9 1.1 0 .4.3.7.8.5.5-.2.9-.6.9-1.1.1-.5-.3-.7-.8-.5zM165.3 11.9c-.5.1-.9.6-1 1.1 0 .5.3.7.8.6.5-.1 1-.6 1-1.1 0-.5-.3-.7-.8-.6zM157.8 13.9c-.5.1-1 .6-1 1.1-.1.5.3.8.8.6.5-.1 1-.6 1-1.1.1-.5-.3-.7-.8-.6zM150.9 15.5c-.5.1-1 .6-1.1 1.1-.1.5.3.8.8.7.5-.1 1-.6 1.1-1.1.1-.5-.2-.8-.8-.7zM144.4 16.9c-.5.1-1 .6-1.1 1.1-.1.5.3.8.8.7.5-.1 1-.6 1.1-1.1.2-.5-.2-.8-.8-.7zM138.3 18.1c-.5.1-1 .6-1.1 1.1-.1.5.3.9.8.8.5-.1 1.1-.6 1.2-1.1.1-.6-.3-.9-.9-.8zM132.2 20.9c.5-.1 1.1-.6 1.2-1.1.1-.5-.3-.9-.8-.8-.5.1-1.1.6-1.2 1.1-.1.6.3.9.8.8zM126 20.9c-.1.5.2.9.8.8.5-.1 1.1-.5 1.2-1.1.1-.5-.3-.9-.8-.8-.6.2-1.1.6-1.2 1.1zM120.7 21.6c-.1.5.2.9.8.8.6-.1 1.1-.5 1.2-1.1.1-.5-.2-.9-.8-.8-.5.1-1.1.6-1.2 1.1zM115.7 22.1c-.1.5.2.9.8.9.5 0 1.1-.5 1.2-1 .1-.5-.2-.9-.8-.8-.5-.1-1 .4-1.2.9zM112.9 22.3c.1-.5-.2-.9-.8-.9-.5.1-1.1.5-1.2 1-.1.5.2.9.8.9.5 0 1.1-.4 1.2-1zM108.3 22.7c.1-.5-.2-.9-.7-.9-.5 0-1.1.5-1.2 1-.1.5.2.9.7.9.5-.1 1.1-.5 1.2-1zM103.8 22.9c.1-.5-.2-.9-.7-.9-.5 0-1.1.5-1.2 1-.1.5.2.9.7.9.5 0 1.1-.5 1.2-1zM99.5 23.1c.1-.5-.2-.9-.7-.9-.5 0-1.1.4-1.2 1-.1.5.2.9.7.9.5-.1 1.1-.5 1.2-1zM94.6 22.3c-.5 0-1.1.4-1.2.9-.2.5.2.9.7.9.5 0 1.1-.4 1.3-.9 0-.5-.3-.9-.8-.9zM91.2 23.3c.2-.5-.2-.9-.7-.9-.5 0-1.1.4-1.3.9-.2.5.1.9.7.9s1.1-.4 1.3-.9zM87.1 23.3c.2-.5-.1-.9-.7-.9-.5 0-1.1.4-1.2.9-.2.5.1.9.7.9.5 0 1.1-.4 1.2-.9zM83.2 23.3c.2-.5-.1-.9-.7-.9-.5 0-1.1.4-1.2.9-.2.5.1.9.7.9.4 0 1-.4 1.2-.9zM78.6 22.4c-.5 0-1.1.4-1.2.9-.2.5.1.9.6.9s1.1-.4 1.2-.9c.2-.5-.1-.9-.6-.9zM74.8 22.3c-.5 0-1.1.4-1.3.9-.2.5.1.9.6.9s1.1-.4 1.3-.9c.2-.5-.1-.9-.6-.9zM71 22.2c-.5 0-1.1.4-1.2.8-.2.5.1.9.6.9s1.1-.4 1.2-.8c.2-.5-.1-.9-.6-.9zM67.2 22.1c-.5 0-1.1.4-1.2.8-.2.5.1.9.6.9s1.1-.4 1.2-.8c.2-.5-.1-.9-.6-.9zM62.2 22.8c-.2.5.1.9.6.9s1.1-.4 1.2-.8c.2-.5-.1-.9-.6-.9s-1.1.4-1.2.8zM58.4 22.7c-.2.5.1.9.6.9s1.1-.4 1.2-.8c.2-.5-.1-.9-.6-.9s-1 .4-1.2.8zM54.6 22.6c-.2.5.1.8.6.9.5 0 1.1-.4 1.2-.8.2-.5-.1-.8-.6-.9-.5 0-1 .4-1.2.8zM50.8 22.5c-.2.5.1.8.6.8s1-.3 1.2-.8c.2-.5-.1-.8-.6-.8s-1 .4-1.2.8zM47 22.5c-.2.5.1.8.6.8s1-.4 1.2-.8c.2-.4-.1-.8-.6-.8s-1 .3-1.2.8zM44.9 22.4c.2-.4-.1-.8-.6-.8s-1 .3-1.2.8c-.2.4.1.8.6.8s1-.3 1.2-.8zM39.2 22.4c-.2.4.1.8.6.8s1-.4 1.2-.8c.2-.4-.1-.8-.5-.8-.6 0-1.1.3-1.3.8zM35.2 22.4c-.2.4.1.8.5.8.5 0 1-.4 1.2-.8.2-.4-.1-.8-.5-.8-.5 0-1 .3-1.2.8zM32.8 22.4c.2-.4-.1-.7-.5-.7-.5 0-1 .3-1.2.8-.2.4.1.8.5.7.5-.1 1.1-.4 1.2-.8zM28.6 22.4c.2-.4-.1-.7-.5-.7-.5 0-1 .3-1.1.8-.2.4.1.7.5.7.5 0 1-.4 1.1-.8zM24.4 22.5c.2-.4-.1-.7-.5-.7-.5 0-1 .3-1.1.7-.2.4.1.7.5.7.4.1.9-.3 1.1-.7zM19.9 22.7c.2-.4-.1-.7-.5-.7s-.9.3-1.1.7c-.2.4.1.7.5.7.5 0 1-.3 1.1-.7zM14.9 22.3c-.4 0-.9.3-1.1.7-.2.4.1.7.5.6.4 0 .9-.4 1.1-.7.1-.3-.1-.6-.5-.6zM10.3 22.8c-.4 0-.9.3-1 .7-.2.4 0 .6.4.6s.8-.4 1-.7c.2-.4 0-.6-.4-.6zM5.6 23.4c-.3 0-.7.3-.8.6-.1.3 0 .5.4.5.3 0 .7-.3.8-.6 0-.4-.1-.6-.4-.5zM.8 24.3c.1-.2 0-.4-.3-.3-.2 0-.4.2-.6.4v.3c.1 0 .1.1.2.1.4-.1.6-.3.7-.5zM182.1.2c.1-.1.3-.1.4-.2h-1.2c.1.3.4.4.8.2zM173.6 1.9c-.5.2-1 .8-1 1.3s.4.7.9.5c.5-.2 1-.8 1-1.3.1-.5-.3-.8-.9-.5zM165.8 4.7c-.5.2-1 .7-1 1.3 0 .5.4.8.9.6.5-.2 1-.7 1-1.3 0-.5-.4-.8-.9-.6zM158.4 7.1c-.6.2-1 .7-1.1 1.3 0 .5.4.8.9.6.6-.2 1.1-.7 1.1-1.3.1-.5-.3-.8-.9-.6zM151.6 9.2c-.6.2-1.1.7-1.1 1.3-.1.5.3.8.9.7.6-.2 1.1-.7 1.1-1.3.1-.6-.3-.9-.9-.7zM145 12.9c.6-.1 1.1-.7 1.2-1.3.1-.6-.4-.9-.9-.7-.6.2-1.1.7-1.1 1.3-.2.5.2.8.8.7zM139.2 12.4c-.6.1-1.1.7-1.2 1.2-.1.5.3.9.9.8.6-.1 1.1-.7 1.2-1.3.1-.5-.3-.9-.9-.7zM133.5 13.6c-.6.1-1.1.7-1.2 1.2-.1.5.3.9.9.8.6-.1 1.1-.7 1.2-1.2.1-.5-.3-.9-.9-.8zM127.7 16.7c.6-.1 1.1-.6 1.2-1.2.1-.6-.3-.9-.9-.8-.6.1-1.1.6-1.2 1.2 0 .5.4.9.9.8zM122.5 17.6c.6-.1 1.1-.6 1.3-1.2.1-.6-.3-.9-.9-.8-.6.1-1.1.6-1.2 1.2-.1.5.3.9.8.8zM117.6 18.3c.6-.1 1.2-.6 1.3-1.2.1-.6-.3-.9-.8-.9-.6.1-1.1.6-1.3 1.1-.2.7.2 1.1.8 1zM114.1 17.8c.1-.6-.2-1-.8-.9-.6.1-1.1.6-1.3 1.1-.1.5.2.9.8.9.6 0 1.1-.6 1.3-1.1zM109.5 18.3c.1-.6-.2-.9-.8-.9-.6.1-1.1.5-1.3 1.1-.1.5.2.9.8.9.5-.1 1.1-.6 1.3-1.1zM105 18.7c.1-.6-.2-1-.8-.9-.6.1-1.1.5-1.3 1.1-.1.5.2 1 .8.9.6-.1 1.2-.6 1.3-1.1zM100.7 19c.1-.5-.2-.9-.8-.9-.6 0-1.1.5-1.3 1-.2.5.2.9.7.9.7 0 1.2-.4 1.4-1zM96.5 19.2c.2-.5-.2-.9-.7-.9-.6 0-1.1.5-1.3 1-.2.5.2.9.7.9.6 0 1.1-.4 1.3-1zM90.4 19.5c-.2.5.2.9.7.9.6 0 1.1-.5 1.3-1 .2-.5-.2-.9-.7-.9-.6 0-1.1.5-1.3 1zM86.4 19.6c-.2.5.1.9.7.9s1.1-.4 1.3-1c.2-.5-.1-.9-.7-.9s-1.1.5-1.3 1zM82.5 19.6c-.2.5.1.9.7.9.5 0 1.1-.4 1.3-.9.2-.5-.1-.9-.7-.9s-1.2.4-1.3.9zM78.6 19.6c-.2.5.1.9.7.9.5 0 1.1-.4 1.3-.9.2-.5-.1-.9-.7-.9s-1.1.4-1.3.9zM74.8 19.6c-.2.5.1.9.6.9s1.1-.4 1.3-.9c.2-.5-.1-.9-.6-.9-.6 0-1.1.4-1.3.9zM72.9 19.6c.2-.5-.1-.9-.6-.9s-1.1.4-1.3.9c-.2.5.1.9.6.9s1.1-.4 1.3-.9zM69.1 19.5c.2-.5-.1-.9-.6-.9s-1.1.4-1.3.9c-.2.5.1.9.6.9.6 0 1.1-.4 1.3-.9zM65.4 19.4c.2-.5-.1-.9-.6-.9s-1.1.4-1.3.8c-.2.5.1.9.6.9.5.1 1.1-.3 1.3-.8zM61.6 19.3c.2-.5-.1-.9-.6-.9s-1.1.4-1.3.8c-.2.5.1.9.6.9.5.1 1.1-.3 1.3-.8zM57.8 19.2c.2-.5-.1-.9-.6-.9s-1.1.4-1.3.8c-.2.5.1.9.6.9.6.1 1.1-.3 1.3-.8zM54 19.1c.2-.5-.1-.8-.6-.9-.5 0-1.1.3-1.3.8-.2.5.1.9.6.9.6.1 1.2-.3 1.3-.8zM50.2 19c.2-.5-.1-.8-.6-.9-.5 0-1.1.3-1.3.8-.2.5.1.8.6.9.6.1 1.1-.3 1.3-.8zM44.5 18.9c-.2.5.1.8.6.8s1.1-.4 1.3-.8c.2-.5-.1-.8-.6-.8s-1.1.4-1.3.8zM42.5 18.9c.2-.4-.1-.8-.6-.8s-1.1.3-1.3.8c-.2.5.1.8.6.8s1.1-.4 1.3-.8zM38.5 18.8c.2-.4 0-.8-.5-.8s-1.1.3-1.3.8c-.2.4.1.8.6.8.4 0 1-.4 1.2-.8zM32.7 18.8c-.2.4.1.8.5.8.5 0 1-.3 1.2-.8.2-.4 0-.8-.5-.8s-1 .3-1.2.8zM28.6 18.8c-.2.4 0 .8.5.8s1-.4 1.2-.8c.2-.4 0-.8-.5-.8s-1 .3-1.2.8zM26.1 18.8c.2-.4 0-.7-.5-.7s-1 .3-1.2.8c-.2.4 0 .7.5.7.4-.1 1-.4 1.2-.8zM20.5 19.6c.5 0 1-.3 1.2-.7.2-.4 0-.7-.5-.7s-1 .3-1.2.7c-.2.4.1.7.5.7zM15.5 19c-.2.4 0 .7.5.7s1-.3 1.1-.7c.2-.4 0-.7-.5-.7-.3 0-.9.4-1.1.7zM11.2 19.4c-.2.4 0 .7.5.7.4 0 .9-.4 1.1-.7.2-.4 0-.7-.4-.7-.6 0-1.1.3-1.2.7zM6.5 19.6c-.2.4 0 .6.4.6s.9-.3 1.1-.7c.2-.4 0-.6-.4-.6-.4.1-.9.4-1.1.7zM2.6 19.4c-.3 0-.7.3-.8.6-.1.3 0 .5.4.5.3 0 .7-.3.8-.6.1-.3 0-.5-.4-.5zM158.9.4c-.6.2-1.1.9-1.1 1.4 0 .6.4.8 1 .6.6-.2 1.1-.9 1.1-1.4 0-.6-.4-.8-1-.6zM152 4.9c.6-.2 1.1-.9 1.2-1.4 0-.6-.4-.9-1-.7-.6.2-1.1.9-1.2 1.4 0 .6.4.9 1 .7zM145.7 7c.6-.2 1.2-.8 1.2-1.4.1-.6-.4-.9-1-.7-.6.2-1.1.8-1.2 1.4-.1.6.4.9 1 .7zM139.7 8.8c.6-.2 1.2-.8 1.2-1.4.1-.6-.4-.9-1-.7-.6.2-1.1.8-1.2 1.4 0 .5.4.9 1 .7zM134 10.4c.6-.1 1.2-.8 1.3-1.3.1-.6-.3-.9-.9-.8-.6.2-1.2.8-1.2 1.3-.2.5.2.9.8.8zM128.6 11.7c.6-.1 1.2-.7 1.3-1.3.1-.6-.3-.9-.9-.8-.6.1-1.2.7-1.3 1.3-.1.5.3.9.9.8zM123.5 12.8c.6-.1 1.2-.7 1.3-1.3.1-.6-.3-1-.9-.8-.6.1-1.2.7-1.3 1.3-.1.5.3.9.9.8zM118.6 13.7c.6-.1 1.2-.7 1.3-1.2.1-.6-.3-1-.9-.8-.6.1-1.2.7-1.3 1.2-.1.5.3.9.9.8zM114.3 12.4c-.6.1-1.2.6-1.3 1.2-.1.6.2 1 .8.9.6-.1 1.2-.6 1.3-1.2.2-.6-.2-1-.8-.9zM110.6 13.9c.1-.6-.2-1-.8-.9-.6.1-1.2.6-1.3 1.2-.1.6.2 1 .8.9.5-.1 1.1-.6 1.3-1.2zM106.2 14.5c.1-.6-.2-1-.8-.9-.6.1-1.2.6-1.3 1.1-.1.6.2 1 .8.9.5 0 1.1-.5 1.3-1.1zM101.9 14.9c.2-.6-.2-1-.8-.9-.6.1-1.2.5-1.3 1.1-.2.5.2 1 .8.9.5 0 1.1-.5 1.3-1.1zM95.6 15.5c-.2.5.2 1 .7.9.6 0 1.2-.5 1.3-1.1.2-.6-.2-1-.8-.9-.4 0-1 .5-1.2 1.1zM91.5 15.7c-.2.5.2 1 .7.9.6 0 1.2-.5 1.3-1 .2-.5-.2-.9-.7-.9-.5 0-1.1.5-1.3 1zM87.6 15.9c-.2.5.1.9.7.9s1.2-.5 1.3-1c.2-.5-.1-.9-.7-.9s-1.2.5-1.3 1zM83.7 16c-.2.5.1.9.7.9s1.2-.5 1.4-1c.2-.5-.1-.9-.7-.9-.7 0-1.3.5-1.4 1zM79.8 16.1c-.2.5.1.9.7.9s1.2-.4 1.3-1c.2-.5-.1-.9-.7-.9-.5 0-1.1.5-1.3 1zM76 16.1c-.2.5.1.9.7.9s1.2-.4 1.3-.9c.2-.5-.1-.9-.7-.9-.5 0-1.1.4-1.3.9zM72.3 16.1c-.2.5.1.9.6.9.6 0 1.2-.4 1.3-.9.2-.5-.1-.9-.6-.9s-1.2.4-1.3.9zM68.5 16c-.2.5.1.9.6.9s1.2-.4 1.3-.9c.2-.5-.1-.9-.6-.9-.5.1-1.1.5-1.3.9zM64.8 16c-.2.5.1.9.6.9s1.1-.4 1.3-.9c.2-.5-.1-.9-.6-.9s-1.1.4-1.3.9zM61.1 15.9c-.2.5.1.9.6.9s1.1-.4 1.3-.9c.2-.5-.1-.9-.6-.9-.5.1-1.1.4-1.3.9zM57.3 15.8c-.2.5.1.9.6.9s1.1-.4 1.3-.8c.2-.5-.1-.9-.6-.9-.4 0-1 .3-1.3.8zM53.6 15.7c-.2.5.1.9.6.9s1.1-.4 1.3-.8c.2-.5-.1-.9-.6-.9s-1.1.3-1.3.8zM49.8 15.6c-.2.5 0 .9.6.9.5 0 1.1-.4 1.3-.8.2-.5 0-.8-.6-.9-.5 0-1.1.3-1.3.8zM46 15.5c-.2.5 0 .8.6.9.5 0 1.1-.4 1.3-.8.2-.5 0-.8-.6-.9-.5 0-1.1.3-1.3.8zM42.2 15.4c-.2.5 0 .8.6.8.5 0 1.1-.3 1.3-.8.2-.4 0-.8-.6-.8-.5 0-1.1.3-1.3.8zM38.3 15.3c-.2.5 0 .8.6.8.5 0 1.1-.3 1.3-.8.2-.4 0-.8-.5-.8-.6 0-1.2.4-1.4.8zM34.3 15.2c-.2.4 0 .8.5.8s1.1-.3 1.3-.8c.2-.4 0-.8-.5-.8s-1.1.4-1.3.8zM30.2 15.2c-.2.4 0 .8.5.8s1.1-.3 1.3-.8c.2-.4 0-.8-.5-.8s-1.1.3-1.3.8zM26.1 15.1c-.2.4 0 .8.5.8s1.1-.3 1.3-.8c.2-.4 0-.8-.5-.8-.6.1-1.1.4-1.3.8zM22.3 15.9c.5 0 1-.3 1.2-.7.2-.4 0-.7-.5-.7s-1 .3-1.3.7c-.1.4.1.7.6.7zM18.6 14.5c-.5 0-1 .3-1.2.7-.2.4 0 .7.5.7s1-.3 1.2-.7c.2-.4 0-.7-.5-.7zM13.1 15.4c-.2.4 0 .7.4.7s1-.3 1.2-.7c.2-.4 0-.7-.4-.7-.5-.1-1 .3-1.2.7zM10.1 15.4c.2-.4 0-.7-.4-.7s-1 .3-1.2.7c-.2.4 0 .7.4.7.5 0 1-.3 1.2-.7zM5.3 15.6c.2-.4 0-.6-.4-.6s-.9.3-1.1.7c-.2.4 0 .7.4.6.4 0 .9-.3 1.1-.7zM146.3 1.2c.5-.2.9-.7 1.1-1.2h-2c-.1.2-.1.3-.2.5 0 .6.4.9 1.1.7zM140.4 3.3c.6-.2 1.2-.9 1.3-1.5.1-.6-.4-.9-1-.7-.6.2-1.2.9-1.2 1.5-.2.6.3.9.9.7zM134.8 5.1c.6-.2 1.2-.8 1.3-1.5.1-.6-.4-.9-1-.7-.6.2-1.2.8-1.3 1.4-.1.6.4 1 1 .8zM129.5 6.6c.6-.2 1.2-.8 1.3-1.4.1-.6-.3-.9-1-.8-.6.2-1.2.8-1.3 1.4-.1.7.3 1 1 .8zM124.4 8c.6-.1 1.2-.8 1.3-1.4.1-.6-.3-1-.9-.8-.6.2-1.2.8-1.3 1.3-.1.6.3 1 .9.9zM119.5 9.1c.6-.1 1.2-.7 1.3-1.3.1-.6-.3-1-.9-.8-.6.1-1.2.7-1.3 1.3-.1.6.3.9.9.8zM114.8 10.1c.6-.1 1.2-.7 1.4-1.3.1-.6-.3-1-.9-.8-.6.1-1.2.7-1.3 1.3-.2.5.2.9.8.8zM110.3 10.9c.6-.1 1.2-.7 1.4-1.2.1-.6-.2-1-.9-.9-.6.1-1.2.7-1.3 1.2-.2.6.2 1 .8.9zM105.9 11.5c.6-.1 1.2-.6 1.4-1.2.1-.6-.2-1-.8-.9-.6.1-1.2.6-1.3 1.2-.3.6.1 1 .7.9zM101.6 12.1c.6-.1 1.2-.6 1.4-1.2.2-.6-.2-1-.8-.9-.6.1-1.2.6-1.4 1.1-.1.6.2 1 .8 1zM96.7 11.6c-.2.6.2 1 .8.9.6-.1 1.2-.6 1.4-1.1.2-.6-.2-1-.8-.9-.6.1-1.2.6-1.4 1.1zM92.7 12c-.2.5.2.9.7.9.6 0 1.2-.5 1.4-1.1.2-.5-.2-.9-.7-.9-.6.1-1.2.5-1.4 1.1zM88.8 12.2c-.2.5.1.9.7.9s1.2-.5 1.4-1c.2-.5-.1-.9-.7-.9-.6.1-1.2.5-1.4 1zM84.9 12.4c-.2.5.1.9.7.9s1.2-.5 1.4-1c.2-.5-.1-.9-.7-.9-.6.1-1.2.5-1.4 1zM81.1 12.6c-.2.5.1.9.7.9s1.2-.4 1.4-1c.2-.5-.1-.9-.7-.9s-1.2.5-1.4 1zM78.7 11.7c-.6 0-1.2.4-1.4.9-.2.5.1.9.7.9s1.2-.4 1.4-.9c.1-.5-.2-.9-.7-.9zM74.9 11.8c-.5 0-1.2.4-1.4.9-.2.5.1.9.6.9.6 0 1.2-.4 1.4-.9.3-.5 0-.9-.6-.9zM69.9 12.7c-.2.5.1.9.6.9s1.2-.4 1.4-.9c.2-.5-.1-.9-.6-.9-.6 0-1.2.4-1.4.9zM66.2 12.7c-.2.5.1.9.6.9s1.2-.4 1.4-.9c.2-.5-.1-.9-.6-.9-.6 0-1.2.4-1.4.9zM62.5 12.6c-.2.5.1.9.6.9s1.2-.4 1.4-.9c.2-.5-.1-.9-.6-.9-.6.1-1.2.4-1.4.9zM58.8 12.5c-.2.5 0 .9.6.9.5 0 1.2-.4 1.4-.8.2-.5 0-.9-.6-.9s-1.2.4-1.4.8zM55.1 12.4c-.2.5 0 .9.6.9.5 0 1.2-.4 1.4-.8.2-.5 0-.9-.6-.9s-1.2.3-1.4.8zM51.4 12.3c-.2.5 0 .9.6.9.5 0 1.2-.4 1.4-.8.2-.5 0-.8-.6-.9-.6 0-1.2.3-1.4.8zM47.6 12.2c-.2.5 0 .8.6.9.5 0 1.1-.3 1.4-.8.2-.5 0-.8-.6-.8-.6-.1-1.2.2-1.4.7zM43.8 12.1c-.2.5 0 .8.6.9.5 0 1.1-.3 1.4-.8.2-.4 0-.8-.5-.8-.7-.1-1.3.2-1.5.7zM39.9 11.9c-.2.4 0 .8.5.8s1.1-.3 1.4-.8c.2-.4 0-.8-.5-.8-.5.1-1.2.4-1.4.8zM36 11.8c-.2.4 0 .8.5.8s1.1-.3 1.3-.8c.2-.4 0-.8-.5-.8s-1.1.4-1.3.8zM32 11.7c-.2.4 0 .8.5.8s1.1-.3 1.3-.8c.2-.4 0-.8-.5-.8s-1.1.4-1.3.8zM29.2 10.9c-.5 0-1.1.3-1.3.7-.2.4 0 .8.5.8s1.1-.3 1.3-.7c.2-.5 0-.8-.5-.8zM23.6 11.5c-.2.4 0 .8.5.8s1.1-.3 1.3-.7c.2-.4 0-.7-.5-.8-.4 0-1 .3-1.3.7zM21.1 11.5c.2-.4 0-.7-.5-.7s-1.1.3-1.3.7c-.2.4 0 .7.5.7s1.1-.3 1.3-.7zM15.6 12.2c.5 0 1-.3 1.2-.7.2-.4 0-.7-.4-.7-.5 0-1 .3-1.2.7-.3.4-.1.7.4.7zM11.1 12.2c.5 0 1-.3 1.2-.7.2-.4 0-.7-.4-.7-.5 0-1 .3-1.2.7-.2.4 0 .7.4.7zM6.4 12.2c.4 0 1-.3 1.2-.7.2-.4 0-.7-.4-.7s-1 .3-1.2.7c-.2.4 0 .7.4.7zM2.6 11.6c.2-.3 0-.6-.4-.6s-.9.3-1.1.6c-.2.4 0 .6.4.6s.9-.3 1.1-.6zM129.3 1c-.1.6.3.9 1 .7.6-.2 1.2-.9 1.3-1.5V0h-1.7c-.3.3-.6.6-.6 1zM125.2 3.3c.6-.2 1.2-.8 1.3-1.4.1-.6-.3-.9-1-.7-.6.2-1.2.8-1.3 1.4 0 .5.4.8 1 .7zM120.4 4.6c.6-.2 1.2-.8 1.4-1.4.1-.6-.3-.9-.9-.8-.6.2-1.2.8-1.3 1.4-.2.6.2.9.8.8zM115.8 5.7c.6-.1 1.2-.7 1.4-1.3.1-.6-.3-.9-.9-.8-.6.2-1.2.7-1.4 1.3-.1.6.3.9.9.8zM111.3 6.7c.6-.1 1.2-.7 1.4-1.3.1-.6-.2-.9-.9-.8-.6.1-1.2.7-1.4 1.3-.1.5.3.9.9.8zM107 7.5c.6-.1 1.2-.7 1.4-1.2.1-.6-.2-.9-.8-.8-.6.1-1.2.7-1.4 1.2-.2.5.2.9.8.8zM102.8 8.2c.6-.1 1.2-.6 1.4-1.2.2-.6-.2-.9-.8-.8-.6.1-1.2.6-1.4 1.2-.2.5.1.9.8.8zM100 7.6c.2-.6-.2-.9-.8-.8-.6.1-1.2.6-1.4 1.1-.2.5.2.9.8.9.7-.1 1.3-.7 1.4-1.2zM95.3 7.2c-.6.1-1.2.5-1.4 1.1-.2.5.1.9.7.9.6-.1 1.2-.5 1.4-1.1.2-.5-.1-.9-.7-.9zM91.4 7.6c-.6.1-1.2.5-1.4 1-.2.5.1.9.7.9s1.2-.5 1.4-1.1c.2-.4-.1-.8-.7-.8zM87.5 8c-.6 0-1.2.5-1.4 1-.2.5.1.9.7.9s1.2-.5 1.4-1c.2-.6-.1-1-.7-.9zM83.8 8.2c-.6 0-1.2.5-1.4 1-.2.5.1.9.7.9s1.2-.5 1.4-1c.1-.5-.2-.9-.7-.9zM78.7 9.3c-.2.5.1.9.6.9.6 0 1.2-.4 1.4-.9.2-.5-.1-.9-.6-.8-.6-.1-1.2.3-1.4.8zM75 9.4c-.2.5.1.9.6.9.6 0 1.2-.4 1.4-.9.2-.5-.1-.9-.6-.8-.6-.1-1.2.3-1.4.8zM72.6 8.6c-.5 0-1.2.4-1.4.9-.2.5.1.9.6.9s1.2-.4 1.4-.9c.3-.5 0-.9-.6-.9zM69 8.6c-.5 0-1.2.4-1.4.8-.2.5 0 .9.6.9.5 0 1.2-.4 1.4-.9.2-.4-.1-.8-.6-.8zM65.3 8.6c-.5 0-1.2.4-1.4.8-.2.5 0 .9.6.9.5 0 1.2-.4 1.4-.8.2-.5 0-.9-.6-.9zM61.7 8.5c-.5 0-1.2.4-1.4.8-.2.5 0 .9.6.9.5 0 1.2-.4 1.4-.8.2-.5-.1-.9-.6-.9zM58 8.5c-.5 0-1.2.3-1.4.8-.2.5 0 .8.6.9.5 0 1.2-.4 1.4-.8.2-.6 0-.9-.6-.9zM54.3 8.4c-.5 0-1.2.3-1.4.8-.2.5 0 .8.6.9.5 0 1.2-.3 1.4-.8.2-.6 0-.9-.6-.9zM50.6 8.2c-.5 0-1.2.3-1.4.8-.2.4 0 .8.5.8s1.2-.3 1.4-.8c.3-.4 0-.7-.5-.8zM46.9 8.1c-.5 0-1.2.3-1.4.8-.2.4 0 .8.5.8s1.2-.3 1.4-.8c.2-.4 0-.8-.5-.8zM43 8c-.5 0-1.2.3-1.4.7-.2.4 0 .8.5.8s1.2-.3 1.4-.8c.3-.3.1-.7-.5-.7zM39.1 7.8c-.5 0-1.1.3-1.4.7-.2.4 0 .8.5.8s1.1-.3 1.4-.7c.3-.4.1-.7-.5-.8zM35.2 7.7c-.5 0-1.2.3-1.4.7-.2.4 0 .8.5.8s1.1-.3 1.4-.7c.2-.4 0-.8-.5-.8zM30.2 9c.5 0 1.1-.3 1.4-.7.2-.4 0-.7-.5-.8-.5 0-1.1.3-1.4.7-.2.5 0 .8.5.8zM26.1 8.9c.5 0 1.1-.3 1.3-.7.2-.4 0-.7-.5-.7s-1.1.3-1.4.7c-.1.3.1.7.6.7zM21.8 8.7c.5 0 1.1-.3 1.3-.7.2-.4 0-.7-.5-.7s-1.1.3-1.3.7c-.2.4 0 .7.5.7zM17.7 8.6c.5 0 1-.3 1.3-.7.2-.4.1-.7-.4-.7s-1.1.3-1.3.7c-.2.3 0 .6.4.7zM13.3 8.4c.5 0 1-.3 1.2-.7.2-.4.1-.7-.4-.7s-1 .3-1.3.6c-.1.5.1.8.5.8zM8.7 8.3c.5 0 1-.3 1.2-.7.3-.3.1-.6-.3-.6-.5 0-1 .3-1.3.6-.2.4 0 .7.4.7zM3.9 8.2c.4 0 1-.3 1.2-.6.2-.3 0-.6-.4-.6s-1 .3-1.2.6c-.2.3 0 .6.4.6zM121.3.2c.1 0 .2-.1.3-.2h-1.1c.2.2.5.3.8.2zM116.7 1.5c.6-.2 1.2-.8 1.4-1.4V0h-1.8c-.2.2-.3.5-.4.7-.2.6.2.9.8.8zM112.3 2.6c.6-.1 1.2-.7 1.4-1.3.1-.6-.2-.9-.9-.8-.6.2-1.2.7-1.4 1.3-.1.6.3.9.9.8zM108 3.6c.6-.1 1.2-.7 1.4-1.3.2-.6-.2-.9-.8-.8-.6.1-1.2.7-1.4 1.3-.1.5.2.9.8.8zM103.9 4.4c.6-.1 1.2-.7 1.4-1.2.2-.6-.2-.9-.8-.8-.6.1-1.2.6-1.4 1.2-.2.5.2.9.8.8zM99.8 5c.6-.1 1.2-.6 1.4-1.2.2-.5-.2-.9-.8-.8-.6.1-1.2.6-1.4 1.1-.1.6.2 1 .8.9zM95.8 5.6c.6-.1 1.2-.6 1.4-1.1.2-.5-.1-.9-.7-.8-.6.1-1.2.6-1.4 1.1-.2.5.2.9.7.8zM92 6c.6-.1 1.2-.5 1.4-1 .2-.5-.1-.9-.7-.8-.6.1-1.2.5-1.4 1-.2.5.1.9.7.8zM88.1 6.4c.6 0 1.2-.5 1.4-1 .2-.5-.1-.8-.7-.8-.6.1-1.2.5-1.4 1-.1.5.2.8.7.8zM84.4 6.7c.6 0 1.2-.5 1.4-1 .2-.5-.1-.8-.6-.8-.6 0-1.2.5-1.4.9-.3.6 0 .9.6.9zM80.7 6.9c.5 0 1.2-.4 1.4-.9.2-.5-.1-.8-.6-.8s-1.2.4-1.4.9c-.3.5 0 .8.6.8zM77 7c.5 0 1.2-.4 1.4-.9.2-.5-.1-.8-.6-.8s-1.2.4-1.4.9c-.2.5 0 .9.6.8zM73.3 7.1c.5 0 1.2-.4 1.4-.9.2-.5 0-.8-.6-.8-.5 0-1.2.4-1.4.8-.2.6.1.9.6.9zM69.7 7.2c.5 0 1.2-.4 1.4-.8.2-.5 0-.8-.6-.8-.5 0-1.2.4-1.4.8-.2.4 0 .8.6.8zM66 7.2c.5 0 1.2-.4 1.4-.8.2-.4 0-.8-.6-.8-.5 0-1.2.4-1.4.8-.2.4.1.8.6.8zM62.4 7.1c.5 0 1.2-.4 1.4-.8.2-.4 0-.8-.5-.8s-1.2.3-1.4.8c-.3.4 0 .8.5.8zM58.8 7c.5 0 1.2-.3 1.4-.8.2-.4 0-.8-.5-.8s-1.2.3-1.4.8c-.3.5-.1.8.5.8zM55.1 6.9c.5 0 1.2-.3 1.4-.8.2-.4 0-.8-.5-.8s-1.2.3-1.4.8c-.3.4 0 .8.5.8zM51.4 6.8c.5 0 1.2-.3 1.4-.8.2-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.3.5 0 .9.5.9zM47.7 6.6c.5 0 1.2-.3 1.4-.7.2-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.3.4 0 .8.5.8zM43.9 6.4c.5 0 1.2-.3 1.4-.7.3-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.2.5 0 .8.5.8zM40.1 6.3c.5 0 1.2-.3 1.4-.7.3-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.3.4 0 .7.5.8zM36.2 6c.5 0 1.2-.3 1.4-.7.3-.4 0-.7-.5-.8-.5 0-1.2.3-1.4.7-.3.5 0 .8.5.8zM32.2 5.8c.5 0 1.2-.3 1.4-.7.3-.4 0-.7-.5-.8-.5 0-1.2.3-1.4.7-.3.5 0 .8.5.8zM28.1 5.6c.5 0 1.1-.3 1.4-.7.2-.4.1-.7-.5-.7-.5 0-1.1.3-1.4.6-.2.5 0 .8.5.8zM23.9 5.4c.5 0 1.1-.3 1.4-.6.3-.4.1-.7-.4-.7s-1.1.3-1.4.6c-.3.3-.1.7.4.7zM20 5.1c.5 0 1.1-.3 1.3-.6.3-.4.1-.7-.4-.7s-1.1.2-1.3.6c-.3.3-.1.7.4.7zM15.7 4.8c.5 0 1-.3 1.3-.6.2-.4.1-.7-.4-.7s-1 .2-1.3.6c-.3.4-.1.7.4.7zM11.2 4.6c.5 0 1-.3 1.3-.6.2-.3.1-.6-.4-.7-.5 0-1 .2-1.3.6-.3.4-.1.7.4.7zM6.4 4.4c.4 0 1-.3 1.2-.6.2-.3.1-.6-.4-.6-.4 0-1 .2-1.3.6-.1.3.1.5.5.6zM2.6 3.2c.2-.3.1-.6-.3-.6s-1 .2-1.2.5c-.3.3-.2.6.3.6.4.1.9-.2 1.2-.5zM105 .6c.4-.1.8-.3 1-.6h-1.8c-.1.5.2.8.8.6zM101 1.4c.6-.1 1.2-.6 1.4-1.2v-.3h-1.6c-.2.2-.4.4-.5.7-.2.6.1.9.7.8zM97.1 2.1c.6-.1 1.2-.6 1.4-1.1.2-.5-.1-.8-.7-.7-.6.1-1.2.6-1.4 1.1-.2.4.1.8.7.7zM93.2 2.6c.6-.1 1.2-.5 1.4-1 .2-.5-.1-.8-.7-.7-.6.1-1.2.5-1.4 1-.1.5.2.8.7.7zM89.4 3.1c.6-.1 1.2-.5 1.4-1 .2-.5-.1-.8-.6-.7-.6.1-1.2.5-1.4 1-.2.4.1.8.6.7zM85.7 3.5c.6 0 1.2-.5 1.4-.9.2-.6-.1-.9-.6-.8-.5.1-1.2.5-1.4.9-.2.5.1.8.6.8zM82 3.7c.5 0 1.2-.4 1.4-.9.2-.5-.1-.8-.6-.7-.5 0-1.1.4-1.4.9-.2.4.1.8.6.7zM78.4 3.9c.5 0 1.1-.4 1.4-.9.2-.4 0-.8-.6-.7-.5 0-1.1.4-1.4.8-.2.5.1.9.6.8zM74.8 4.1c.5 0 1.1-.4 1.4-.8.2-.4 0-.8-.6-.7-.5 0-1.1.4-1.4.8-.2.3 0 .7.6.7zM71.2 4.2c.5 0 1.1-.4 1.4-.8.2-.4 0-.8-.5-.8s-1.1.4-1.4.8c-.3.4-.1.8.5.8zM67.6 4.2c.5 0 1.2-.4 1.4-.8.2-.4 0-.8-.5-.8s-1.2.3-1.4.8c-.3.4 0 .8.5.8zM64 4.2c.5 0 1.2-.3 1.4-.8.2-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.3.5 0 .9.5.9zM60.4 4.1c.5 0 1.2-.3 1.4-.7.2-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.3.4 0 .8.5.8zM56.8 4c.5 0 1.2-.3 1.4-.7.3-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.3.4-.1.8.5.8zM53.1 3.9c.5 0 1.2-.3 1.4-.7.3-.4 0-.8-.5-.8s-1.2.3-1.4.7c-.2.4 0 .8.5.8zM49.5 3.7c.5 0 1.2-.3 1.5-.7.3-.4 0-.8-.5-.8s-1.2.3-1.5.7c-.3.4-.1.8.5.8zM45.7 3.5c.5 0 1.2-.3 1.4-.7.3-.4.1-.7-.5-.8-.5 0-1.2.3-1.5.7-.1.4.1.8.6.8zM42 3.3c.5 0 1.2-.3 1.4-.7.3-.4.1-.7-.5-.8-.5 0-1.2.3-1.5.7-.2.4 0 .8.6.8zM38.1 3.1c.5 0 1.2-.3 1.4-.6.3-.4.1-.7-.5-.7-.5 0-1.2.2-1.4.6-.2.3 0 .6.5.7zM34.2 2.8c.5 0 1.2-.3 1.4-.6.3-.4.1-.7-.4-.7s-1.2.2-1.4.6c-.3.3-.1.7.4.7zM30.2 2.5c.5 0 1.1-.2 1.4-.6.3-.4.1-.7-.4-.7s-1.1.2-1.4.6c-.3.4-.1.7.4.7zM26.1 2.3c.5 0 1.1-.2 1.4-.6.2-.4 0-.7-.4-.7-.5 0-1.1.2-1.4.6-.3.3-.1.6.4.7zM22.3 1.8c.5 0 1.1-.2 1.3-.6.3-.3.1-.7-.4-.7s-1.1.2-1.3.6c-.3.3-.1.7.4.7zM18.1 1.5c.5 0 1-.2 1.3-.6.3-.3.1-.6-.3-.7-.5 0-1 .2-1.3.5-.4.4-.2.7.3.8zM13.7 1.1c.4 0 1-.2 1.3-.5.2-.2.1-.4 0-.6h-1c-.3.1-.6.2-.7.4-.2.4-.1.7.4.7zM9.1.8c.4 0 1-.2 1.2-.5.1-.1.1-.2.1-.2H8.9c-.1-.1-.1 0-.2 0-.2.4-.1.6.4.7zM87.1.4c.3 0 .6-.2.9-.4h-1.5c0 .2.2.4.6.4zM83.5.7c.5 0 1-.3 1.2-.7h-1.8c-.2.4 0 .8.6.7zM79.9 1c.5 0 1.1-.4 1.4-.8V.1h-1.8c-.1.1-.2.2-.2.3-.2.3 0 .6.6.6zM75.7.4c-.2.4 0 .7.5.7s1.1-.4 1.4-.8c.1-.1.1-.3.1-.4h-1.5l-.5.5zM72.2.6c-.2.4 0 .7.5.7s1.1-.4 1.4-.8c.1-.2.1-.4 0-.5h-1.2c-.3.1-.6.3-.7.6zM68.7.6c-.2.4 0 .7.5.7s1.1-.3 1.4-.8c.2-.3.1-.5-.1-.6h-.9c-.4.2-.8.5-.9.7zM65.1.6c-.3.4 0 .7.5.7S66.7 1 67 .6c.2-.3.1-.5-.1-.6h-.8c-.4.1-.8.3-1 .6zM61.6.6c-.3.4 0 .7.5.7s1.2-.3 1.4-.7c.2-.3.1-.5-.1-.6h-1c-.3.1-.6.3-.8.6zM58 .5c-.3.4 0 .7.5.7s1.2-.3 1.4-.7c.1-.2.1-.4 0-.5h-1.3c-.2.1-.4.3-.6.5zM54.4.4c-.3.4-.1.7.5.8.5 0 1.2-.3 1.4-.7.1-.2.1-.3.1-.4h-1.6c-.1 0-.3.1-.4.3zM51.3 1c.5 0 1.2-.3 1.5-.7.1-.1.1-.2.1-.3H51c-.1.1-.2.1-.2.2-.3.4 0 .7.5.8zM47.6.7c.5 0 1.2-.3 1.5-.6V0h-2c-.2.4 0 .7.5.7zM43.9.5c.5 0 1-.2 1.3-.5h-1.9c0 .3.2.5.6.5zM40.1.3c.3 0 .7-.1 1-.3h-1.5c.1.1.3.2.5.3z"/></svg>\n        <a style="text-decoration:none; ' +
                //         this.linkcolor +
                //         '" href="https://www.mcmaster.ca/">' +
                //         this.FooterLogo +
                //         '<span class="sr-only">McMaster logo</span></a>\n        <ul id="mcmaster--links">\n          <li><a style="' +
                //         this.linkcolor +
                //         '"  href="https://www.mcmaster.ca/opr/html/opr/contact_us/main/contact_us.html">Contact</a></li>\n          <li><a style="' +
                //         this.linkcolor +
                //         '"  href="https://www.mcmaster.ca/opr/html/footer/main/terms_of_use.html">Terms &amp; Conditions</a></li>\n          <li><a style="' +
                //         this.linkcolor +
                //         '"  href="https://www.mcmaster.ca/privacy/">Privacy Policy</a></li>\n        </ul>\n       ' +
                //         this.social +
                //         '\n        <ul id="address--links">\n          <li><a style="' +
                //         this.linkcolor +
                //         '"  href="https://www.google.ca/maps/place/McMaster+University/@43.260879,-79.919225,17z/data=%213m1%214b1%214m2%213m1%211s0x882c84ac44f72ac1:0x399e00ea6143011c" target="_blank">1280 Main Street West&emsp;&nbsp;Hamilton, Ontario&nbsp;&nbsp;L8S 4L8</a></li>\n          <li><a style="' +
                //         this.linkcolor +
                //         '"  href="tel:+19055259140"><strong>(905) 525-9140</strong></a></li>\n        </ul>\n          <p class="copyright"><a style="' +
                //         this.linkcolor +
                //         '"  href="https://www.mcmaster.ca/">&copy; ' +
                //         this.getyear() +
                //         " McMaster University</a></p>\n        </footer>"),
                //     this.footer
                // );
            },
        }, {
            key: "getstyles",
            value: function() {
                return ((this.styles = "#mcmaster-header,#mcmaster-header *{box-sizing:border-box;-moz-box-sizing:border-box}#mcmaster-header{overflow:hidden;background:" + this.headerColor + ';width: 100%; font-family: "Roboto Condensed", Arial, sans-serif; font-size: 16px;}\n        #mcmaster-header {\n          font-size: 10px;\n        }\n        body.noscroll {\n          overflow-y: hidden;\n        }\n        #mcmaster-header .nav-item {\n          margin: 0;\n          display: inline-block;\n          position: relative;\n          //min-width: 75px;\n          min-width: 80px;\n          text-align: center;\n          //height: 100px;\n          transition: all 0.3s ease-out, min-width 0s;\n          text-transform: none;\n          color: #5b6770;\n          font-size: 11px;\n          font-weight: 800;\n          letter-spacing: 0.04em;\n          cursor: pointer;\n          z-index: 1500;\n          border-bottom: 3px solid transparent;\n        }\n\n          #mcmaster-header,\n        #mcmaster-header * {\n        box-sizing: border-box;\n        -moz-box-sizing: border-box;\n        }\n\n\n        // #mcmaster-header .nav-item:hover, #mcmaster-header .nav-item:focus {\n        //   background-color: rgba(0, 0, 0, 0.05);\n        //   text-decoration: none;\n        //   border-bottom-color: #ac1455;\n        // }\n\n       /* ===MAC SEARCH ICON=== */\n       #mcmaster-search {\n         //padding-top: 65px;\n         padding-top: 52px;\n       }\n       #mcmaster-search span,\n       #mcmaster-search span::after,\n       #mcmaster-search span::before {\n         -webkit-transition: .25s ease-in-out;\n         transition: .25s ease-in-out;\n       }\n       #mcmaster-search span {\n         display: block;\n         position: absolute;\n         height: 24px;\n         width: 24px;\n         border: 3px solid ' + this.headerIcnsColor + ";\n         border-radius: 50%;\n         // top: 25px;\n         top: 12px;\n         left: 30%;\n       }\n       #mcmaster-search span:before {\n         position: absolute;\n         display: block;\n         left: 20px;\n         bottom: -7px;\n         border-radius: 2px;\n         width: 12px;\n         height: 3px;\n         background: " + this.headerIcnsColor + ";\n         content: '';\n         -webkit-transform: translateX(-6px) translateY(-3px) rotate(45deg);\n         -ms-transform: translateX(-6px) translateY(-3px) rotate(45deg);\n         transform: translateX(-6px) translateY(-3px) rotate(45deg);\n       }\n       #mcmaster-search span:after {\n         position: absolute;\n         display: block;\n         left: 20px;\n         bottom: -7px;\n         border-radius: 2px;\n         width: 12px;\n         height: 3px;\n         background: " + this.headerIcnsColor + ";\n         content: '';\n         -webkit-transform: translateX(-6px) translateY(-3px) rotate(45deg);\n         -ms-transform: translateX(-6px) translateY(-3px) rotate(45deg);\n         transform: translateX(-6px) translateY(-3px) rotate(45deg);\n       }\n       /*    Mac Search Icon Active */\n       #mcmaster-header.search-active #mcmaster-search span {\n         height: 0%;\n         width: 0%;\n         //top: 36px;\n         top: 25px;\n         left: 35px;\n\n         border: 2px solid " + this.headerIcnsColorAlt + ";\n       }\n       #mcmaster-header.search-active #mcmaster-search span:before {\n         left: -15px;\n         bottom: -2px;\n         width: 32px;\n         transform: rotate(-135deg);\n         background: " + this.headerIcnsColorAlt + ";\n       }\n       #mcmaster-header.search-active #mcmaster-search span:after {\n         left: -16px;\n         bottom: -2px;\n         width: 32px;\n         transform: rotate(135deg);\n         background: " + this.headerIcnsColorAlt + ";\n       }\n       #mcmaster-header.search-active #mcmenu span,\n       #mcmaster-header.search-active #mcmenu span:before,\n       #mcmaster-header.search-active #mcmenu span:after {\n        background: " + this.headerIcnsColorAlt + ";\n       }\n       /* ===MAC MENU ICON=== */\n       #mcmenu {\n         transform: rotate(0deg);\n         transition: .5s ease-in-out;\n         cursor: pointer;\n         //padding-top: 65px;\n         padding-top: 52px;\n       }\n       #mcmenu span {\n         display: block;\n         position: absolute;\n         height: 3px;\n         width: 32px;\n         background: " + this.headerIcnsColor + ";\n          -webkit-transition: .25s ease-in-out;\n          transition: .25s ease-in-out;\n         border-radius: 2px;\n         opacity: 1;\n         top: 36px;\n         left: 28%;\n       }\n       #mcmenu span,\n       #mcmenu span::before,\n       #mcmenu span::after {\n         -webkit-transition: .25s ease-in-out;\n         transition: .25s ease-in-out;\n         border-radius: 2px;\n       }\n       #mcmenu span::before,\n       #mcmenu span::after {\n         position: absolute;\n         display: block;\n         left: 0;\n         width: 32px;\n         height: 3px;\n         background: " + this.headerIcnsColor + ';\n         content: \'\';\n       }\n       #mcmenu span:before {\n         top: -8px;\n       }\n       #mcmenu span:after {\n         top: 8px;\n       }\n       /* Mac Menu Icon Active */\n       #mcmaster-header.menu-active #mcmenu span {\n         transform: rotate(180deg);\n       }\n       #mcmaster-header.menu-active #mcmenu span:before {\n         top: -8px;\n         width: 16px;\n         left: 4px;\n         transform: translateX(-6px) translateY(3px) rotate(-45deg);\n       }\n       #mcmaster-header.menu-active #mcmenu span:after {\n         top: 8px;\n         width: 16px;\n         left: 4px;\n         transform: translateX(-6px) translateY(-3px) rotate(45deg);\n       }\n       #mcmaster-header.menu-active #mcmenu span,\n       #mcmaster-header.menu-active #mcmenu span:before,\n       #mcmaster-header.menu-active #mcmenu span:after {\n         background: #5e6a71 !important;\n       }\n       #mcmaster-header.menu-active #mcmenu {\n         color: #5e6a71;\n         background: #f0f0f0;\n       }\n       /* Mac Menu Icon Active (search icon) */\n       #mcmaster-header.menu-active #mcmaster-search {\n         color: #5e6a71 !important;\n         background: #f0f0f0;\n       }\n       #mcmaster-header.menu-active #mcmaster-search span {\n         border-color: #5e6a71 !important;\n       }\n       #mcmaster-header.menu-active #mcmaster-search span:before,\n       #mcmaster-header.menu-active #mcmaster-search span:after {\n         background: #5e6a71 !important;\n       }\n\n      .sr-only {\n        height: 1px;\n        padding: 0px;\n        margin: -1px;\n        overflow: hidden;\n        clip: rect(0px, 0px, 0px, 0px);\n        border: 0px none;\n        position: absolute;\n        width: 1px;\n      }\n\n\n      /* ===OFF CANVAS MENU=== */\n    #mcmaster-nav {\n      background: #f0f0f0;\n      border-left: 1px solid #f0f0f0;\n      position: fixed;\n      padding: 0;\n      margin: 0;\n      //padding-top: 100px;\n      padding-top: 142px;\n      width: 240px;\n      height:100%;\n      top: 0;\n      right: -240px;\n      z-index: 1021;\n      //margin-top: 0;\n      -webkit-overflow-scrolling: touch;\n      -webkit-transition: all 0.3s ease-out;\n      transition: all 0.3s ease-out;\n      // box-shadow: -5px 0px 10px rgba(0,0,0,0.1);\n    }\n    #mcmaster-nav:before {\n      display:block;\n      background: #7a003c;\n      height: 142px;\n      position: absolute;\n      content: \'\';\n    }\n\n    #mcmaster-nav a {\n      display: inline-block;\n      outline:none;\n      width: 100%;\n      color: #5e6a71;\n      padding: 10px 20px 10px 20px;\n      border-top: 1px solid #f0f0f0;\n      font-weight: 300;\n      font-size: 15px;\n      background: #fff;\n      text-decoration:none;\n    }\n\n\n    // header#mcmaster-header.menu-active #navLinks {\n    //   right: 100px;\n    // }\n\n\n\n    #mcmaster-nav>li>a {\n      font-size: 20px;\n      outline:none;\n      padding: 15px 20px 15px 20px;\n      background: #f0f0f0;\n      border-top-color: #d9d9d9;\n    }\n    #mcmaster-nav a:hover, #mcmaster-nav a:focus {\n      background: #e8e8e8;\n    }\n    #mcmaster-nav>li>a:hover, #mcmaster-nav>li>a:focus {\n      background: #5e6a71;\n      color: #fff;\n    }\n    #mcmaster-nav li,\n    #mcmaster-nav ul {\n      list-style-image: none;\n      list-style-type: none;\n      margin: 0;\n      padding: 0;\n    }\n    #mcmaster-header.menu-active #mcmaster-nav {\n      -webkit-transform: translate(-240px, 0);\n      -ms-transform: translate(-240px, 0);\n      transform: translate(-240px, 0);\n    }\n    // header#mcmaster-header.menu-active .header__inner #navLinks {\n    //     position: fixed !important;\n    //     top: 42px;\n    //     right: 2%;\n    // }\n    #mcmaster-nav input {\n      display: none;\n    }\n    #mcmaster-nav label {\n      cursor: pointer;\n      display: block;\n      font-size: 20px;\n      padding: 15px 20px 15px 20px;\n      background: #7a003c;\n      border-top: 1px solid #37001a;\n      z-index: 20;\n      color: #fff;\n      font-weight: 300;\n    }\n    #mcmaster-nav label:hover, #mcmaster-nav label:focus {\n      background: #ac1455;\n    }\n    #mcmaster-nav input:checked + label {\n      background: #ac1455;\n    }\n    #mcmaster-nav ul {\n      background: #f7f7f7;\n      overflow: hidden;\n      z-index: 10;\n      height: 0;\n      overflow: hidden;\n      -webkit-transition: max-height 0.8s;\n      -moz-transition: max-height 0.8s;\n      transition: max-height 0.8s;\n    }\n    #mcmaster-nav input:checked ~ ul {\n      max-height: 720px;\n    }\n\n     #mcmaster-header.condensed{overflow:visible;height:60px}#mcmaster-header.condensed #mcmenu,#mcmaster-header.condensed #mcmaster-search{text-indent:-9999px;height:60px}#mcmaster-header.condensed #mcmaster-brand{height:60px}#mcmaster-header.condensed #mcmaster-search{padding-top:5px;}#mcmaster-header.condensed #mcmenu{padding-top:5px;}#mcmaster-header.condensed #mcmaster-logo{width:140px !important;height:auto !important}#mcmaster-header.condensed #mcmaster-logo:hover{border-bottom-color:transparent!important;background-color:transparent!important}#mcmaster-header.condensed #mcmenu span{top:28px}#mcmaster-header.condensed #mcmaster-search span{top:14px}#mcmaster-header.condensed.search-active #mcmaster-search span{top:27px}\n     #mac-footer{width:100%;box-sizing:border-box;padding:10px;text-align:center;font-family:"Roboto Condensed",Arial,sans-serif;font-size:12px;line-height:15px}#mac-footer ul{margin:12px 0;padding:0;list-style-type:none;text-align:center}#mac-footer ul#mcmaster--links{margin: 20px 0;} #mac-footer ul li{display:inline;padding:5px;white-space:nowrap}#mac-footer ul li a{text-decoration:none;color:#5e6a71}#mac-footer ul li a:hover{text-decoration:underline}#mac-footer #mcmaster-logo{max-width:425px;height:auto;margin-top:5px}\n     footer#mac-footer { position: relative; } footer#mac-footer * { z-index: 1; position: relative; }footer#mac-footer #radiance { position: absolute; top: 0; left: 0; z-index: 0; max-width: 460px;} footer#mac-footer a { text-decoration: none; } footer#mac-footer a:hover { text-decoration: underline; } footer#mac-footer { background-color: #7a003c !important; /*height: 432px;*/ font-family: "Roboto Condensed",Arial, "Helvetica Neue", Helvetica, sans-serif; padding: 1em 2em 2.7em; text-align: center; font-size: 14px; } footer#mac-footer .footer__inner { max-width: 1218px; margin: 0 auto; } footer#mac-footer .footer__logo { /*display: flex; justify-content: center*/ } footer#mac-footer svg#mcmaster-logo g#letters, footer#mac-footer svg#mcmaster-logo g#brighterworld, footer#mac-footer svg#mcmaster-logo path#shieldoutline { fill: white; } footer#mac-footer svg#mcmaster-logo path#divider { stroke: white; stroke-width: 2; } footer#mac-footer svg#mcmaster-logo path#bookspine, footer#mac-footer svg#mcmaster-logo path#shield { fill: #5e6a71; } footer#mac-footer svg#mcmaster-logo g#bookoutline, footer#mac-footer svg#mcmaster-logo path#books, footer#mac-footer svg#mcmaster-logo g#leaves, footer#mac-footer svg#mcmaster-logo g#shieldbg { fill: #ffbc3d; } footer#mac-footer svg#mcmaster-logo path#bookbg, footer#mac-footer svg#mcmaster-logo path#bookspine_1_, footer#mac-footer svg#mcmaster-logo g#eagle { fill: #7a003c; } /* Mockup logo is off center */ footer#mac-footer .footer__logo > img { /*margin-left: 14px;*/ max-width: 100%; } footer#mac-footer .footer__logo svg { border-right: 1px solid #fff; padding: 20px; } footer#mac-footer .footer__logo h2 { color: #fff; padding: 20px; text-align: left; } footer#mac-footer ul { list-style-type: none; padding-left: 0; } footer#mac-footer ul#mcmaster--links, footer#mac-footer ul#social--links, footer#mac-footer ul#address--links { /*display: flex; justify-content: center;*/ } footer#mac-footer ul#mcmaster--links li, footer#mac-footer ul#social--links li, footer#mac-footer ul#address--links li { display: inline-block; } footer#mac-footer ul#mcmaster--links { margin-top: 1.6em; margin-bottom: 1.6em; border-top: 1px solid rgba(255,255,255,0.2); border-bottom: 1px solid rgba(255,255,255,0.2); /*padding: 1rem 0;*/ } footer#mac-footer ul#mcmaster--links li { line-height: 24px; } footer#mac-footer ul#mcmaster--links li a { display: block; padding: 1em 3em; font-family: "Roboto Condensed","Arial Narrow", Arial, sans-serif; text-transform: none; font-weight: 900; letter-spacing: 1px; } footer#mac-footer ul#social--links a:hover { border-color: #fdbf57; } footer#mac-footer ul#social--links a { height: 32px; width: 32px; border: 2px solid rgba(255,255,255,0.8); /*display: flex; justify-content: center; align-items: center;*/ border-radius: 50%; margin: 0 15px; -webkit-transition: background 250ms; -o-transition: background 250ms; transition: background 250ms; margin-bottom: 4px; display: table; -webkit-box-sizing: border-box; box-sizing: border-box; } footer#mac-footer ul#social--links a svg { max-width: 20px; display: table-cell; text-align: center; vertical-align: middle; height: 28px; margin: 0 auto; } footer#mac-footer ul#social--links a svg * { -webkit-transition: all 150ms; -o-transition: all 150ms; transition: all 150ms; fill: #fff; } footer#mac-footer ul#social--links a:hover svg * { fill: #fdbf57 !important; } footer#mac-footer li { margin-left: 0; } footer#mac-footer a { color: #fff; } footer#mac-footer a.footer__logo { color: rgba(0,0,0,0); } footer#mac-footer ul#address--links { margin-bottom: 1.3em; } footer#mac-footer ul#address--links a { padding: 6px 4px; display: block; font-weight: 300; letter-spacing: 0.5px; } footer#mac-footer p.copyright { color: #fff; font-size: 0.75em; letter-spacing: 0.75px; } @media (max-width: 768px) { footer#mac-footer ul#mcmaster--links li{ display: block; padding: 0; } footer#mac-footer ul#social--links a { margin: 0 4px 4px } footer#mac-footer ul#mcmaster--links li a { padding: 0.25em 3em; } footer#mac-footer ul#mcmaster--links { padding: 1.25em 0 1.375em; } }\n\n    .noscroll {\n        \n    }\n\n\n\n    #skiptocontent a {\n      padding: 6px;\n      position: absolute;\n      top: -40px;\n      left: 0px;\n      color: #FFF!important;\n      border-right: 1px solid white;\n      border-bottom: 1px solid white;\n      border-bottom-right-radius: 8px;\n      background: #000!important;\n      transition: top 1s ease-out, background 1s linear;\n      z-index: 999;\n    }\n\n    #skiptocontent a:focus {\n      position: absolute;\n      left: 0px;\n      top: 0px;\n      background-color: #BF1722;\n      outline: 0;\n      transition: top .1s ease-in, background .5s linear;\n    }\n\n\n    header#mcmaster-header {\n      background: #fff;\n      padding-top: 24px;\n      padding-bottom: 16px;\n      // box-shadow: 0px 0px 30px 4px rgba(0,0,0,0.1);\n    }\n    header#mcmaster-header.condensed #mcmaster-brand {\n      height: 76px\n    }\n    header#mcmaster-header #mcmaster-header__title {\n      display: block;\n      z-index: 1;\n      /*position: absolute;*/\n      text-align: center;\n      top: 0;\n      left: 0;\n      width: calc(100vw - (360px + 8%));\n      margin: 0 auto;\n      max-width: 900px;\n      // position: relative;\n      // z-index: 1400;\n    }\n    header#mcmaster-header .mcmaster-header__department,\n    header#mcmaster-header .mcmaster-header__tagline {\n      text-transform: none;\n      text-decoration: none;\n      color: #7a003c;\n      font-family: "Roboto Condensed","Arial Narrow", Arial, sans-serif;\n      letter-spacing: 1px;\n      font-weight: 900;\n      font-size: 2em;\n      //line-height: 0.875;\n      //line-height: 1.5625em;\n      line-height: 1.6;\n      //margin: 0.4em 0 0.4em 0;\n      margin: 0;\n      // margin: 0 0 24px 0;\n      clear: none;\n    }\n    header#mcmaster-header .mcmaster-header__tagline {\n      margin-bottom: 16px;\n    }\n    header#mcmaster-header .mcmaster-header__department > a,\n    header#mcmaster-header .mcmaster-header__department > a:hover,\n    header#mcmaster-header .mcmaster-header__department > a:visited {\n      text-decoration: none;\n      color: #7a003c;\n    }\n    header#mcmaster-header .mcmaster-header__header-title {\n      font-family: "Roboto Condensed","Arial Narrow", Arial, sans-serif;\n      font-size: 3.8em;\n      text-decoration: none;\n      letter-spacing: 1px;\n      line-height: 1.2631578947;\n      margin: 0 0 24px 0;\n      //margin: 0 0 8px 0;\n      font-weight: 400;\n      color: #1a1c1d;\n      clear: none;\n    }\n    header#mcmaster-header .mcmaster-header__header-title.has-tagline {\n      margin-bottom: 8px;\n    }\n    header#mcmaster-header .mcmaster-header__header-title > a,\n    header#mcmaster-header .mcmaster-header__header-title > a:visited,\n    header#mcmaster-header .mcmaster-header__header-title > a:hover {\n      text-decoration: none;\n      color: #1a1c1d;\n    }\n    header#mcmaster-header .mcmaster-header__header-title.title-only {\n      text-transform: uppercase;\n      font-size: 4em;\n      letter-spacing: 1px;\n      line-height: 1.2em;\n      padding-top: 0.4em;\n    }\n    header#mcmaster-header .header__inner {\n      /*max-width: 1460px;*/\n      padding-left: 4%;\n      padding-right: 4%;\n      margin: 0 auto;\n      position: relative;\n    }\n    header#mcmaster-header .header__inner #navLinks {\n      position: absolute;\n      top: 0;\n      right: 0;\n      transition: width 0s, right 0.3s ease-out;\n    }\n    header#mcmaster-header #navLinks {\n      position: absolute;\n      top: 32px;\n      right: 4%;\n    }\n    header#mcmaster-header svg#mcmaster-logo g#letters * {\n      fill: #5e6a71 !important;\n    }\n    header#mcmaster-header #mcmenu,\n    header#mcmaster-header #mcmaster-search {\n      height: 72px;\n  font-size: 1rem; font-weight:normal\n    }\n    header#mcmaster-header #mcmaster-search:before,\n    header#mcmaster-header #mcmenu:before {\n      text-transform: none;\n      text-indent: 0;\n      display: block;\n      position: absolute;\n      color: #5e6a71;\n      width: 100%;\n      text-align: center;\n      font-family: \'Roboto\', \'RegCon\', "Arial Narrow", Arial, sans-serif;\n      bottom: 0;\n      transition: all 250ms;\n      line-height: 1.3em;\n      font-size: 14px;\n      font-weight: 400;\n      letter-spacing: 1px;\n      border-bottom: 2px solid rgba(0,0,0,0);\n      transition: border-bottom 250ms ease-out;\n      padding-bottom: 4px;\n      margin-bottom: -4px;\n    }\n    header#mcmaster-header a#mcmaster-search:hover:before,\n    header#mcmaster-header a#mcmenu:hover:before {\n        border-bottom: 2px solid #5e6a71;\n    }\n\n    header#mcmaster-header.menu-active #mcmaster-search:before,\n    header#mcmaster-header.menu-active #mcmenu:before {\n      color: #5e6a71;\n    }\n\n    header#mcmaster-header #mcmaster-search span:before,\n    header#mcmaster-header #mcmaster-search span:after {\n      left: 20px;\n      bottom: -6px;\n      width: 10px;\n    }\n    header#mcmaster-header #mcmenu span,\n    header#mcmaster-header #mcmenu span::before,\n    header#mcmaster-header #mcmenu span::after {\n      width: 22px;\n    }\n    header#mcmaster-header #mcmenu span {\n      //top: 28px;\n      top: 26px;\n      //left: 30%;\n      left: 28px;\n    }\n    header#mcmaster-header .mcmaster-header__site-logo {\n      max-height: 76px;\n      max-width: 100% !important;\n    }\n    header#mcmaster-header .mcmaster-header__site-logo[src*="nursing"] {\n      height: 76px;\n    }\n    header#mcmaster-header .mcmaster-header__site-logo[src*="brighter-world"] {\n      height: 64px;\n      margin-top: 16px;\n    }\n    header#mcmaster-header .mcmaster-header__site-logo[src*="business"] {\n      height: 66px;\n      margin-top: 16px;\n    }\n    header#mcmaster-header .mcmaster-header__site-logo[src*="cmcr"],\n    header#mcmaster-header .mcmaster-header__site-logo[src*="medicine"],\n    header#mcmaster-header .mcmaster-header__site-logo[src*="daily-news"],\n    header#mcmaster-header .mcmaster-header__site-logo[src*="brand-standards"] {\n      height: 56px;\n      margin-top: 16px;\n    }\n\n    // #mcmenu span:before {\n    //   top: -8px;\n    // }\n    // #mcmenu span:after {\n    //   top: 8px;\n    // }\n    @media (max-width: 768px) {\n      header#mcmaster-header {\n        background: #fff;\n        padding-top: 0;\n        padding-bottom: 34px;\n      }\n      header#mcmaster-header #navLinks {\n        top: 8px;\n      }\n      /*header#mcmaster-header #mcmaster-header__title {\n        position: static;\n        clear: both;\n      }*/\n      header#mcmaster-header #navLinks {\n        margin-bottom: 1em;\n      }\n      footer#mac-footer #radiance {\n        display: none;\n      }\n      @supports (transform: rotate(180deg)) {\n        footer#mac-footer #radiance {\n          transform: rotate(180deg);\n          display: block;\n          bottom: 0;\n          right: 0;\n          top: auto;\n          left: auto;\n        }\n      }\n    }\n\n    @media (max-width: 768px) {\n      header#mcmaster-header #mcmaster-header__title {\n        position: static;\n        clear: both;\n        width: 100%;\n        padding-top: 16px;\n      }\n      header#mcmaster-header .mcmaster-header__header-title {\n        margin-bottom: 0;\n      }\n      header#mcmaster-header .header__inner {\n        padding-left: 4%;\n        padding-right: 4%;\n      }\n      header#mcmaster-header #navLinks {\n        right: 2%;\n      }\n      footer#mac-footer ul#social--links li {\n        padding: 2px;\n      }\n      div#navLinks {\n        width: 120px !important;;\n      }\n      #mcmaster-header .nav-item {\n        min-width: 60px !important;\n      }\n      #mcmaster-header.search-active #mcmaster-search span {\n        left: 29px;\n      }\n      header#mcmaster-header #mcmenu span {\n        left: 20px;\n      }\n    }\n\n    @media (max-width: 359px) {\n      #mcmaster-logo-header-st-joes {\n        height: 40px !important;\n      }\n    }\n\n    @media (max-width: 425px) {\n      header#mcmaster-header #mcmaster-search:before,\n      header#mcmaster-header #mcmenu:before {\n        content: \'\';\n      }\n    }\n\n    // @supports (display: flex) {\n    //   @media (max-width: 768px) {\n    //     footer#mac-footer ul#social--links {\n    //       display: flex;\n    //       flex-wrap: wrap;\n    //       justify-content: center;\n    //     }\n    //     footer#mac-footer ul#social--links li {\n    //       flex-basis: 30%;\n    //     }\n    //     footer#mac-footer ul#social--links li a {\n    //       margin: 0 auto 4px;\n    //     }\n    //   }\n    // }\n    '),
                this.styles);
            },
        }, {
            key: "getSearchHtmlCSS",
            value: function() {
                var c = '\n\n      /* ===SEARCH OVERLAY=== */\n    #mcmaster-search-overlay {\n      position: fixed;\n      display: block;\n      width: 100%;\n      height: 100%;\n      height: calc(100% - 100px);\n      top: 100px;\n      left: 0;\n      z-index: 1100;\n      overflow-y: scroll !important;\n      background-color: #c6cbce;\n    }\n    #mcmaster-search-overlay .btn-group {\n      display: block;\n      margin: 10px auto !important;\n    }\n    #mcmaster-search-overlay .btn-group .btn {\n      float: none;\n    }\n    #mcmaster-search-overlay .btn-group .btn:first-child,\n    #mcmaster-search-overlay .btn-group .btn+.btn {\n      margin-left: 10px\n    }\n    \n    #mcmaster-search-form {\n      width: 90%;\n      max-width: 600px;\n      margin: 0 auto;\n      font-size: 16px;\n      border-bottom: 1px solid rgba(0,0,0,0.1);\n      padding-bottom: 24px;\n    }\n    #mcmaster-search-form button {\n      font-size: 1em;\n      font-family: "Roboto Condensed","Arial Narrow", Arial, sans-serif;\n    }\n\n\n    /*Results box */\n    .gsc-control-cse {\n    border-color: transparent !important;\n    background-color: transparent !important;\n}\n\n\n    #mcmaster-header #mcmaster-search-overlay {\n      top: 0px !important;\n      height: 100%;\n    }\n    /* Transition Effects */\n    #mcmaster-search-overlay {\n      opacity: 0;\n      visibility: hidden;\n      -webkit-transition: opacity 0.5s, visibility 0s 0.5s;\n      transition: opacity 0.5s, visibility 0s 0.5s;\n    }\n    #mcmaster-header.search-active #mcmaster-search-overlay {\n      opacity: 1;\n      visibility: visible;\n      -webkit-transition: opacity 0.5s;\n      transition: opacity 0.5s;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links {\n      opacity: 0.4;\n      -webkit-transform: translateY(-25%) rotateX(35deg);\n      transform: translateY(-25%) rotateX(35deg);\n      -webkit-transition: -webkit-transform 0.5s, opacity 0.5s;\n      transition: transform 0.5s, opacity 0.5s;\n    }\n    #mcmaster-header.search-active #mcmaster-search-overlay #mcmaster-quick-links {\n      opacity: 1;\n      -webkit-transform: rotateX(0deg);\n      transform: rotateX(0deg);\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links {\n      -webkit-transform: translateY(25%) rotateX(-35deg);\n      transform: translateY(25%) rotateX(-35deg);\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links ul {\n      padding-left: 40px;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links li {\n      list-style-type: disc;\n    }\n    /* Search Field */\n    #mcmaster-search-overlay #search-input {\n      padding: 3px;\n      border: solid 1px #E4E4E4;\n      border-radius: 6px;\n      background-color: #fff;\n      margin: 0 auto;\n      //margin-top: 80px;\n      margin-top: 142px;\n      -webkit-transform: translateY(-50%);\n      -ms-transform: translateY(-50%);\n      transform: translateY(-50%);\n      -webkit-perspective: 1200px;\n      perspective: 1200px;\n      height: 50px;\n    }\n    #mcmaster-search-overlay #search-input {\n      opacity: 0.4;\n      -webkit-transform: translateY(-25%) rotateX(35deg);\n      transform: translateY(-25%) rotateX(35deg);\n      -webkit-transition: -webkit-transform 0.5s, opacity 0.5s;\n      transition: transform 0.5s, opacity 0.5s;\n    }\n    #mcmaster-header.search-active #mcmaster-search-overlay #search-input {\n      opacity: 1;\n      -webkit-transform: rotateX(0deg);\n      transform: rotateX(0deg);\n    }\n    #mcmaster-search-overlay #search-input {\n      -webkit-transform: translateY(25%) rotateX(-35deg);\n      transform: translateY(25%) rotateX(-35deg);\n    }\n    #mcmaster-search-overlay #search-input input {\n      border: 0;\n      box-shadow: none;\n      font-size: 18px;\n      padding: 10px 45px 10px 10px;\n      color: #1e252b;\n      width: 100% !important;\n    }\n    #mcmaster-search-overlay #search-input button {\n      display: block;\n      width: 60px;\n      height: 48px;\n      margin: 0;\n      background: none;\n      box-shadow: none;\n      border: 0;\n      padding: 9px;\n      border-left: none !important;\n      position:absolute;\n      right: 0;\n      top: 0;\n    }\n    #mcmaster-search-overlay #search-input button svg {\n      width: 30px;\n      height: 30px;\n    }\n    #mcmaster-search-overlay #search-input button .search-icon {\n      fill: #5e6a71;\n    }\n    #mcmaster-search-overlay #search-input button:hover .search-icon {\n      fill: #7a003c;\n    }\n    /* Quick Links */\n    #mcmaster-search-overlay #mcmaster-quick-links {\n      display: block;\n      background: #fff;\n      padding: 15px 15px;\n      border-top: 5px solid #7a003c;\n      box-shadow: 0 2px 10px #8e979d;\n      overflow-y: scroll;\n      margin-bottom: 50px;\n      width: 90%;\n      max-width: 600px;\n      margin: 0 auto;\n      margin-top: 50px;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links .link-row {\n      margin: 0;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links .link-row .column {\n      width: 50%;\n      float: left;\n      min-width: 255px;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links .links-title {\n      font-size: 18px;\n      line-height: 20px;\n      margin-top: 20px;\n      margin-bottom: 20px;\n      text-transform: none;\n      padding-left: 20px;\n      font-family: "Roboto Condensed", Arial, sans-serif;\n      font-weight: 800;\n      color: #5e6a71;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links ul li a {\n      display: inline;\n      color: #ac1455;\n      font-size: 16px;\n      line-height: 20px;\n      text-transform: none;\n      letter-spacing: 0;\n      text-decoration: none;\n      border-bottom: none;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links ul li a:hover {\n      color: #147cac;\n      background: none;\n      text-decoration: none;\n    }\n    #mcmaster-search-overlay #mcmaster-quick-links li {\n      margin-bottom: 5px;\n      padding-right: 10px;\n    }\n    .btn.btn-mac-search,\n    .btn-mac-search {\n        width: 277px !important;\n        //height: 30px !important;\n        height: 50px !important;\n        padding: 0 !important;\n        margin-top: 5px !important;\n        margin: 10px;\n        border-radius: 50px !important;\n    }\n\n  .btn-primary.btn-mac-search {\n      color: #fff;\n      background-color: #7A003C !important;\n      border-color: transparent !important;\n      cursor:pointer;\n  }\n\n  .sr-only {\n    position: absolute !important;\n    width: 1px;\n    height: 1px;\n    padding: 0;\n    margin: -1px;\n    overflow: hidden;\n    clip: rect(0,0,0,0);\n    border: 0;\n  }\n\n\n    #clearSearch{cursor:pointer}\n    '
                  , e = document.createElement("style");
                e.innerHTML = c;
                this.domainSearch;
                document.head.appendChild(e),
                (this.overlayStr = '<div id="mcmaster-search-form">\n\n            <form id="frmSearch" name="search_form">\n              <div id="search-input">\n              <div class="input-group" style="width:100%;">\n              <label for="keyword" class="sr-only">Keyword Search</label>\n              <input name="q" id="keyword" class="form-control input-lg" placeholder="Type your keyword here" type="text">\n              <span id="clearAll" class="input-group-btn"><button type="button" class="btn btn-info btn-lg" id=\'clearSearch\' style="display:none"><svg id="seach-icon-svg" xmlns="https://www.w3.org/2000/svg" viewBox="0 0 40 40"><path class="close-x" d="M 10,10 L 30,30 M 30,10 L 10,30"></path></svg><span class="sr-only">Clear search</span></button></span>\n              </div>\n              </div>\n              <div class="btn-group">\n\n              <button id=\'btnSearchDomain\' type="submit" class="btn btn-primary btn-mac-search" name="hq" value="inurl:' + window.location.host + '">Search Current Website</button>\n              <button id="btnMcMaster" type="submit" class="btn btn-primary btn-mac-search" name="hq" value="inurl:mcmaster.ca">Search McMaster</button>\n              </div>\n            </form>\n\n\n\n      </div>\n        <div class="link-row">\n          <div id=\'___gcse_0\' style="width: 90%; max-width: 600px; margin: 0 auto;">\n            <div id="results"></div>\n          </div>\n        </div>\n      <div id="mcmaster-quick-links">\n        <div class="link-row">\n          <div class="column">\n            <h2 class="links-title">Tools</h2>\n            <ul class="list-unstyled">\n              <li><a href="https://www.mcmaster.ca/opr/html/a_z/main/a_z_index.html">A-Z Campus Index</a> </li>\n              <li><a href="https://registrar.mcmaster.ca/askmcmaster/">Ask McMaster</a> </li>\n              <li> <a href="https://future.mcmaster.ca/tours/virtual/">Virtual Tour</a> </li>\n              <li><a href="https://www.mcmaster.ca/welcome/findus.cfm">How to get to McMaster</a> </li>\n              <li><a href="https://directories.mcmaster.ca/faculty-staff/">Faculty and Staff Directory</a> </li>\n              <li><a href="https://csprd.mcmaster.ca/psp/prcsprd/?cmd=login">Mosaic</a> </li>\n            </ul>\n          </div>\n          <div class="column">\n            <h2 class="links-title">Faculties</h2>\n            <ul class="list-unstyled">\n              <li><a href="https://www.degroote.mcmaster.ca/">DeGroote School of Business</a> </li>\n              <li><a href="https://www.eng.mcmaster.ca/">Faculty of Engineering</a> </li>\n              <li><a href="https://fhs.mcmaster.ca/">Faculty of Health Sciences</a> </li>\n              <li><a href="https://www.humanities.mcmaster.ca/">Faculty of Humanities</a> </li>\n              <li><a href="https://www.science.mcmaster.ca/">Faculty of Science</a> </li>\n              <li><a href="https://socialsciences.mcmaster.ca/">Faculty of Social Sciences</a> </li>\n            </ul>\n          </div>\n        </div>\n        <div class="link-row">\n          <div class="column">\n            <h2 class="links-title">Students</h2>\n            <ul class="list-unstyled">\n              <li><a href="https://registrar.mcmaster.ca/">Current Students</a> </li>\n              <li><a href="https://future.mcmaster.ca/">Future Students</a> </li>\n              <li><a href="https://oia.mcmaster.ca/portal/">International Students</a> </li>\n              <li><a href="https://studentsuccess.mcmaster.ca">Student Success Centre</a> </li>\n              <li><a href="https://future.mcmaster.ca/programs/viewbook/">McMaster Viewbook</a> </li>\n              <li><a href="https://continuing.mcmaster.ca/">McMaster Continuing Education</a> </li>\n              <li><a href="https://wellness.mcmaster.ca/">Student Wellness Centre</a> </li>\n            </ul>\n          </div>\n          <div class="column">\n            <h2 class="links-title">Campus Life</h2>\n            <ul class="list-unstyled">\n              <li><a href="https://alumni.mcmaster.ca/">Alumni</a> </li>\n              <li><a href="https://www.marauders.ca/">Athletics</a> </li>\n              <li><a href="https://library.mcmaster.ca/">Libraries</a> </li>\n              <li><a href="https://csprd.mcmaster.ca/psp/prcsprd/?cmd=login">Mosaic</a> </li>\n              <li><a href="https://research.mcmaster.ca/">Research</a> </li>\n              <li><a href="https://alumni.os.mcmaster.ca/s/1439/index.aspx?sid=1439&amp;gid=1&amp;pgid=323">Give to McMaster</a> </li>\n            </ul>\n          </div>\n        </div>\n      </div>');
                var t = document.createElement("div");
                t.setAttribute("id", "mcmaster-search-overlay"),
                t.setAttribute("aria-label", "Site Search and Quick Links"),
                (t.innerHTML = this.overlayStr);
                var a = document.getElementById("mcmaster-header");
                a.insertAdjacentHTML("beforeend", t.outerHTML);
            },
        }, {
            key: "searchReady",
            value: function() {
                document.onreadystatechange = function() {
                    if ("complete" === document.readyState) {
                        var c = (document.getElementById("mcmaster-search-form"),
                        document.getElementById("mcmaster-quick-links"))
                          , e = document.getElementById("clearSearch")
                          , t = document.getElementById("results");
                        e && e.addEventListener("click", function(a) {
                            (c.style.display = "block"),
                            (e.style.display = "none"),
                            (t.style.display = "none");
                        });
                    }
                }
                ;
            },
        }, {
            key: "setSearchCustom",
            value: function(c) {
                (c = this.sanitize(r, c)),
                (this.domainSearch = c);
            },
        }, {
            key: "getHeader",
            value: function() {
                var c = this;
                // this.header =
                //     this.font +
                //     '\n         <header id="mcmaster-header">' +
                //     this.skiplinks +
                //     '\n          <div class="header__inner">\n            <a href="//www.mcmaster.ca" id="mcmaster-brand" class="nav-item" style="float:left;display:block; z-index:1000; position:relative; padding-top: 8px;">' +
                //     this.getLogo(1, this.grayLogoCol) +
                //     '<span class="sr-only">McMaster logo</span></a>\n            <div id="mcmaster-header__title">\n              ' +
                //     this.title +
                //     '\n            </div>\n          </div>\n           <div id="navLinks" style="float:right; width:160px; z-index:1200; position:absolute; transition: width 0s;">\n            <a href="//www.mcmaster.ca" role="button" aria-controls="mcmaster-search-overlay" id="mcmaster-search" class="nav-item"><span></span>SEARCH</a><a href="#" id="mcmenu" class="nav-item" role="button" aria-controls="mcmaster-nav" aria-expanded="false"><span></span>MENU</a>\n          </div>\n        </header>';
                var e = setInterval(function() {
                    if (null != document.querySelector("#mcmaster-header")) {
                        c.getSearchHtmlCSS();
                        document.getElementById("btnSearchDomain");
                        "" == c.domainSearch && (c.domainSearch = "mcmaster.ca"),
                        clearInterval(e),
                        document.getElementById("btnSearchDomain").addEventListener("click", function(e) {
                            var t = document.getElementById("keyword").value;
                            c.gcseCallback(c.domainSearch, t),
                            e.preventDefault();
                        }),
                        document.getElementById("btnMcMaster").addEventListener("click", function(e) {
                            var t = document.getElementById("keyword").value;
                            c.gcseCallback("mcmaster.ca", t),
                            e.preventDefault();
                        });
                    }
                }, 100);
                return this.header;
            },
        }, {
            key: "insertAfter",
            value: function(c, e) {
                c.parentNode.insertBefore(e, c.nextSibling);
            },
        }, {
            key: "getJson",
            value: function(c, e) {
                return new Promise(function(t, a) {
                    var s = new XMLHttpRequest();
                    s.open("GET", c),
                    (e = {}),
                    (s.onload = function() {
                        200 == s.status ? t(s.response) : a(Error(s.statusText));
                    }
                    ),
                    (s.onerror = function() {
                        a(Error("Network Error"));
                    }
                    ),
                    s.send();
                }
                );
            },
        }, ]),
        c);
    }
    )();
}
, function(c, e, t) {
    "use strict";
    !(function(e, t) {
        c.exports = t();
    }
    )(void 0, function() {
        function c(c, e) {
            for (var t = e.length; t--; )
                "string" == typeof e[t] && (e[t] = e[t].toLowerCase()),
                (c[e[t]] = !0);
            return c;
        }
        function e(c) {
            var e = {}
              , t = void 0;
            for (t in c)
                Object.prototype.hasOwnProperty.call(c, t) && (e[t] = c[t]);
            return e;
        }
        function t(c) {
            if (Array.isArray(c)) {
                for (var e = 0, t = Array(c.length); e < c.length; e++)
                    t[e] = c[e];
                return t;
            }
            return Array.from(c);
        }
        function a() {
            var u = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : z()
              , f = function(c) {
                return a(c);
            };
            if (((f.version = "1.0.2"),
            (f.removed = []),
            !u || !u.document || 9 !== u.document.nodeType))
                return (f.isSupported = !1),
                f;
            var M = u.document
              , g = !1
              , v = !1
              , b = u.document
              , x = u.DocumentFragment
              , y = u.HTMLTemplateElement
              , k = u.Node
              , w = u.NodeFilter
              , A = u.NamedNodeMap
              , L = void 0 === A ? u.NamedNodeMap || u.MozNamedAttrMap : A
              , _ = u.Text
              , V = u.Comment
              , S = u.DOMParser
              , H = u.XMLHttpRequest
              , C = void 0 === H ? u.XMLHttpRequest : H
              , E = u.encodeURI
              , T = void 0 === E ? u.encodeURI : E;
            if ("function" == typeof y) {
                var F = b.createElement("template");
                F.content && F.content.ownerDocument && (b = F.content.ownerDocument);
            }
            var I = b
              , Z = I.implementation
              , N = I.createNodeIterator
              , B = I.getElementsByTagName
              , O = I.createDocumentFragment
              , R = M.importNode
              , D = {};
            f.isSupported = Z && "undefined" != typeof Z.createHTMLDocument && 9 !== b.documentMode;
            var q = null
              , j = c({}, [].concat(t(s), t(n), t(r), t(o), t(l)))
              , Y = null
              , G = c({}, [].concat(t(i), t(m), t(h), t(d)))
              , U = null
              , X = null
              , P = !0
              , W = !0
              , Q = !1
              , J = !1
              , K = !1
              , $ = /\{\{[\s\S]*|[\s\S]*\}\}/gm
              , cc = /<%[\s\S]*|[\s\S]*%>/gm
              , ec = !1
              , tc = !1
              , ac = !1
              , sc = !1
              , nc = !1
              , rc = !1
              , oc = !0
              , lc = !0
              , ic = {}
              , mc = c({}, ["audio", "head", "math", "script", "style", "template", "svg", "video"])
              , hc = c({}, ["audio", "video", "img", "source", "image"])
              , dc = c({}, ["alt", "class", "for", "id", "label", "name", "pattern", "placeholder", "summary", "title", "value", "style", "xmlns"])
              , pc = null
              , zc = b.createElement("form")
              , uc = function(a) {
                "object" !== ("undefined" == typeof a ? "undefined" : p(a)) && (a = {}),
                (q = "ALLOWED_TAGS"in a ? c({}, a.ALLOWED_TAGS) : j),
                (Y = "ALLOWED_ATTR"in a ? c({}, a.ALLOWED_ATTR) : G),
                (U = "FORBID_TAGS"in a ? c({}, a.FORBID_TAGS) : {}),
                (X = "FORBID_ATTR"in a ? c({}, a.FORBID_ATTR) : {}),
                (ic = "USE_PROFILES"in a && a.USE_PROFILES),
                (P = a.ALLOW_ARIA_ATTR !== !1),
                (W = a.ALLOW_DATA_ATTR !== !1),
                (Q = a.ALLOW_UNKNOWN_PROTOCOLS || !1),
                (J = a.SAFE_FOR_JQUERY || !1),
                (K = a.SAFE_FOR_TEMPLATES || !1),
                (ec = a.WHOLE_DOCUMENT || !1),
                (sc = a.RETURN_DOM || !1),
                (nc = a.RETURN_DOM_FRAGMENT || !1),
                (rc = a.RETURN_DOM_IMPORT || !1),
                (ac = a.FORCE_BODY || !1),
                (oc = a.SANITIZE_DOM !== !1),
                (lc = a.KEEP_CONTENT !== !1),
                K && (W = !1),
                nc && (sc = !0),
                ic && ((q = c({}, [].concat(t(l)))),
                (Y = []),
                ic.html === !0 && (c(q, s),
                c(Y, i)),
                ic.svg === !0 && (c(q, n),
                c(Y, m),
                c(Y, d)),
                ic.svgFilters === !0 && (c(q, r),
                c(Y, m),
                c(Y, d)),
                ic.mathMl === !0 && (c(q, o),
                c(Y, h),
                c(Y, d))),
                a.ADD_TAGS && (q === j && (q = e(q)),
                c(q, a.ADD_TAGS)),
                a.ADD_ATTR && (Y === G && (Y = e(Y)),
                c(Y, a.ADD_ATTR)),
                a.ADD_URI_SAFE_ATTR && c(dc, a.ADD_URI_SAFE_ATTR),
                lc && (q["#text"] = !0),
                Object && "freeze"in Object && Object.freeze(a),
                (pc = a);
            }
              , fc = function(c) {
                f.removed.push({
                    element: c
                });
                try {
                    c.parentNode.removeChild(c);
                } catch (e) {
                    c.outerHTML = "";
                }
            }
              , Mc = function(c, e) {
                f.removed.push({
                    attribute: e.getAttributeNode(c),
                    from: e
                }),
                e.removeAttribute(c);
            }
              , gc = function(c) {
                var e = void 0
                  , t = void 0;
                if ((ac && (c = "<remove></remove>" + c),
                v)) {
                    try {
                        c = T(c);
                    } catch (c) {}
                    var a = new C();
                    (a.responseType = "document"),
                    a.open("GET", "data:text/html;charset=utf-8," + c, !1),
                    a.send(null),
                    (e = a.response);
                }
                if (g)
                    try {
                        e = new S().parseFromString(c, "text/html");
                    } catch (c) {}
                return (e && e.documentElement) || ((e = Z.createHTMLDocument("")),
                (t = e.body),
                t.parentNode.removeChild(t.parentNode.firstElementChild),
                (t.outerHTML = c)),
                B.call(e, ec ? "html" : "body")[0];
            };
            f.isSupported && !(function() {
                var c = gc('<svg><g onload="this.parentNode.remove()"></g></svg>');
                c.querySelector("svg") || (v = !0);
                try {
                    (c = gc('<svg><p><style><img src="</style><img src=x onerror=alert(1)//">')),
                    c.querySelector("svg img") && (g = !0);
                } catch (c) {}
            }
            )();
            var vc = function(c) {
                return N.call(c.ownerDocument || c, c, w.SHOW_ELEMENT | w.SHOW_COMMENT | w.SHOW_TEXT, function() {
                    return w.FILTER_ACCEPT;
                }, !1);
            }
              , bc = function(c) {
                return (!(c instanceof _ || c instanceof V) && !("string" == typeof c.nodeName && "string" == typeof c.textContent && "function" == typeof c.removeChild && c.attributes instanceof L && "function" == typeof c.removeAttribute && "function" == typeof c.setAttribute));
            }
              , xc = function(c) {
                return "object" === ("undefined" == typeof k ? "undefined" : p(k)) ? c instanceof k : c && "object" === ("undefined" == typeof c ? "undefined" : p(c)) && "number" == typeof c.nodeType && "string" == typeof c.nodeName;
            }
              , yc = function(c, e, t) {
                D[c] && D[c].forEach(function(c) {
                    c.call(f, e, t, pc);
                });
            }
              , kc = function(c) {
                var e = void 0;
                if ((yc("beforeSanitizeElements", c, null),
                bc(c)))
                    return fc(c),
                    !0;
                var t = c.nodeName.toLowerCase();
                if ((yc("uponSanitizeElement", c, {
                    tagName: t,
                    allowedTags: q
                }),
                !q[t] || U[t])) {
                    if (lc && !mc[t] && "function" == typeof c.insertAdjacentHTML)
                        try {
                            c.insertAdjacentHTML("AfterEnd", c.innerHTML);
                        } catch (c) {}
                    return fc(c),
                    !0;
                }
                return (!J || c.firstElementChild || (c.content && c.content.firstElementChild) || !/</g.test(c.textContent) || (f.removed.push({
                    element: c.cloneNode()
                }),
                (c.innerHTML = c.textContent.replace(/</g, "&lt;"))),
                K && 3 === c.nodeType && ((e = c.textContent),
                (e = e.replace($, " ")),
                (e = e.replace(cc, " ")),
                c.textContent !== e && (f.removed.push({
                    element: c.cloneNode()
                }),
                (c.textContent = e))),
                yc("afterSanitizeElements", c, null),
                !1);
            }
              , wc = /^data-[\-\w.\u00B7-\uFFFF]/
              , Ac = /^aria-[\-\w]+$/
              , Lc = /^(?:(?:(?:f|ht)tps?|mailto|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
              , _c = /^(?:\w+script|data):/i
              , Vc = /[\u0000-\u0020\u00A0\u1680\u180E\u2000-\u2029\u205f\u3000]/g
              , Sc = function(c) {
                var e = void 0
                  , t = void 0
                  , a = void 0
                  , s = void 0
                  , n = void 0
                  , r = void 0
                  , o = void 0;
                if ((yc("beforeSanitizeAttributes", c, null),
                (r = c.attributes))) {
                    var l = {
                        attrName: "",
                        attrValue: "",
                        keepAttr: !0,
                        allowedAttributes: Y
                    };
                    for (o = r.length; o--; ) {
                        if (((e = r[o]),
                        (t = e.name),
                        (a = e.value.trim()),
                        (s = t.toLowerCase()),
                        (l.attrName = s),
                        (l.attrValue = a),
                        (l.keepAttr = !0),
                        yc("uponSanitizeAttribute", c, l),
                        (a = l.attrValue),
                        "name" === s && "IMG" === c.nodeName && r.id))
                            (n = r.id),
                            (r = Array.prototype.slice.apply(r)),
                            Mc("id", c),
                            Mc(t, c),
                            r.indexOf(n) > o && c.setAttribute("id", n.value);
                        else {
                            if ("INPUT" === c.nodeName && "type" === s && "file" === a && (Y[s] || !X[s]))
                                continue;
                            "id" === t && c.setAttribute(t, ""),
                            Mc(t, c);
                        }
                        if (l.keepAttr && (!oc || ("id" !== s && "name" !== s) || !(a in u || a in b || a in zc))) {
                            if ((K && ((a = a.replace($, " ")),
                            (a = a.replace(cc, " "))),
                            W && wc.test(s)))
                                ;
                            else if (P && Ac.test(s))
                                ;
                            else {
                                if (!Y[s] || X[s])
                                    continue;
                                if (dc[s])
                                    ;
                                else if (Lc.test(a.replace(Vc, "")))
                                    ;
                                else if (("src" !== s && "xlink:href" !== s) || 0 !== a.indexOf("data:") || !hc[c.nodeName.toLowerCase()]) {
                                    if (Q && !_c.test(a.replace(Vc, "")))
                                        ;
                                    else if (a)
                                        continue;
                                } else
                                    ;
                            }
                            try {
                                c.setAttribute(t, a),
                                f.removed.pop();
                            } catch (c) {}
                        }
                    }
                    yc("afterSanitizeAttributes", c, null);
                }
            }
              , Hc = function c(e) {
                var t = void 0
                  , a = vc(e);
                for (yc("beforeSanitizeShadowDOM", e, null); (t = a.nextNode()); )
                    yc("uponSanitizeShadowNode", t, null),
                    kc(t) || (t.content instanceof x && c(t.content),
                    Sc(t));
                yc("afterSanitizeShadowDOM", e, null);
            };
            return ((f.sanitize = function(c, e) {
                var t = void 0
                  , a = void 0
                  , s = void 0
                  , n = void 0
                  , r = void 0;
                if ((c || (c = "<!-->"),
                "string" != typeof c && !xc(c))) {
                    if ("function" != typeof c.toString)
                        throw new TypeError("toString is not a function");
                    c = c.toString();
                }
                if (!f.isSupported) {
                    if ("object" === p(u.toStaticHTML) || "function" == typeof u.toStaticHTML) {
                        if ("string" == typeof c)
                            return u.toStaticHTML(c);
                        if (xc(c))
                            return u.toStaticHTML(c.outerHTML);
                    }
                    return c;
                }
                if ((tc || uc(e),
                (f.removed = []),
                c instanceof k))
                    (t = gc("<!-->")),
                    (a = t.ownerDocument.importNode(c, !0)),
                    1 === a.nodeType && "BODY" === a.nodeName ? (t = a) : t.appendChild(a);
                else {
                    if (!sc && !ec && c.indexOf("<") === -1)
                        return c;
                    if (((t = gc(c)),
                    !t))
                        return sc ? null : "";
                }
                ac && fc(t.firstChild);
                for (var o = vc(t); (s = o.nextNode()); )
                    (3 === s.nodeType && s === n) || kc(s) || (s.content instanceof x && Hc(s.content),
                    Sc(s),
                    (n = s));
                if (sc) {
                    if (nc)
                        for (r = O.call(t.ownerDocument); t.firstChild; )
                            r.appendChild(t.firstChild);
                    else
                        r = t;
                    return rc && (r = R.call(M, r, !0)),
                    r;
                }
                return ec ? t.outerHTML : t.innerHTML;
            }
            ),
            (f.setConfig = function(c) {
                uc(c),
                (tc = !0);
            }
            ),
            (f.clearConfig = function() {
                (pc = null),
                (tc = !1);
            }
            ),
            (f.addHook = function(c, e) {
                "function" == typeof e && ((D[c] = D[c] || []),
                D[c].push(e));
            }
            ),
            (f.removeHook = function(c) {
                D[c] && D[c].pop();
            }
            ),
            (f.removeHooks = function(c) {
                D[c] && (D[c] = []);
            }
            ),
            (f.removeAllHooks = function() {
                D = {};
            }
            ),
            f);
        }
        var s = ["a", "abbr", "acronym", "address", "area", "article", "aside", "audio", "b", "bdi", "bdo", "big", "blink", "blockquote", "body", "br", "button", "canvas", "caption", "center", "cite", "code", "col", "colgroup", "content", "data", "datalist", "dd", "decorator", "del", "details", "dfn", "dir", "div", "dl", "dt", "element", "em", "fieldset", "figcaption", "figure", "font", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr", "html", "i", "img", "input", "ins", "kbd", "label", "legend", "li", "main", "map", "mark", "marquee", "menu", "menuitem", "meter", "nav", "nobr", "ol", "optgroup", "option", "output", "p", "pre", "progress", "q", "rp", "rt", "ruby", "s", "samp", "section", "select", "shadow", "small", "source", "spacer", "span", "strike", "strong", "style", "sub", "summary", "sup", "table", "tbody", "td", "template", "textarea", "tfoot", "th", "thead", "time", "tr", "track", "tt", "u", "ul", "var", "video", "wbr", ]
          , n = ["svg", "a", "altglyph", "altglyphdef", "altglyphitem", "animatecolor", "animatemotion", "animatetransform", "audio", "canvas", "circle", "clippath", "defs", "desc", "ellipse", "filter", "font", "g", "glyph", "glyphref", "hkern", "image", "line", "lineargradient", "marker", "mask", "metadata", "mpath", "path", "pattern", "polygon", "polyline", "radialgradient", "rect", "stop", "style", "switch", "symbol", "text", "textpath", "title", "tref", "tspan", "video", "view", "vkern", ]
          , r = ["feBlend", "feColorMatrix", "feComponentTransfer", "feComposite", "feConvolveMatrix", "feDiffuseLighting", "feDisplacementMap", "feFlood", "feFuncA", "feFuncB", "feFuncG", "feFuncR", "feGaussianBlur", "feMerge", "feMergeNode", "feMorphology", "feOffset", "feSpecularLighting", "feTile", "feTurbulence", ]
          , o = ["math", "menclose", "merror", "mfenced", "mfrac", "mglyph", "mi", "mlabeledtr", "mmuliscripts", "mn", "mo", "mover", "mpadded", "mphantom", "mroot", "mrow", "ms", "mpspace", "msqrt", "mystyle", "msub", "msup", "msubsup", "mtable", "mtd", "mtext", "mtr", "munder", "munderover", ]
          , l = ["#text"]
          , i = ["accept", "action", "align", "alt", "autocomplete", "background", "bgcolor", "border", "cellpadding", "cellspacing", "checked", "cite", "class", "clear", "color", "cols", "colspan", "coords", "datetime", "default", "dir", "disabled", "download", "enctype", "face", "for", "headers", "height", "hidden", "high", "href", "hreflang", "id", "ismap", "label", "lang", "list", "loop", "low", "max", "maxlength", "media", "method", "min", "multiple", "name", "noshade", "novalidate", "nowrap", "open", "optimum", "pattern", "placeholder", "poster", "preload", "pubdate", "radiogroup", "readonly", "rel", "required", "rev", "reversed", "role", "rows", "rowspan", "spellcheck", "scope", "selected", "shape", "size", "span", "srclang", "start", "src", "step", "style", "summary", "tabindex", "title", "type", "usemap", "valign", "value", "width", "xmlns", ]
          , m = ["accent-height", "accumulate", "additivive", "alignment-baseline", "ascent", "attributename", "attributetype", "azimuth", "basefrequency", "baseline-shift", "begin", "bias", "by", "class", "clip", "clip-path", "clip-rule", "color", "color-interpolation", "color-interpolation-filters", "color-profile", "color-rendering", "cx", "cy", "d", "dx", "dy", "diffuseconstant", "direction", "display", "divisor", "dur", "edgemode", "elevation", "end", "fill", "fill-opacity", "fill-rule", "filter", "flood-color", "flood-opacity", "font-family", "font-size", "font-size-adjust", "font-stretch", "font-style", "font-variant", "font-weight", "fx", "fy", "g1", "g2", "glyph-name", "glyphref", "gradientunits", "gradienttransform", "height", "href", "id", "image-rendering", "in", "in2", "k", "k1", "k2", "k3", "k4", "kerning", "keypoints", "keysplines", "keytimes", "lang", "lengthadjust", "letter-spacing", "kernelmatrix", "kernelunitlength", "lighting-color", "local", "marker-end", "marker-mid", "marker-start", "markerheight", "markerunits", "markerwidth", "maskcontentunits", "maskunits", "max", "mask", "media", "method", "mode", "min", "name", "numoctaves", "offset", "operator", "opacity", "order", "orient", "orientation", "origin", "overflow", "paint-order", "path", "pathlength", "patterncontentunits", "patterntransform", "patternunits", "points", "preservealpha", "r", "rx", "ry", "radius", "refx", "refy", "repeatcount", "repeatdur", "restart", "result", "rotate", "scale", "seed", "shape-rendering", "specularconstant", "specularexponent", "spreadmethod", "stddeviation", "stitchtiles", "stop-color", "stop-opacity", "stroke-dasharray", "stroke-dashoffset", "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-opacity", "stroke", "stroke-width", "style", "surfacescale", "tabindex", "targetx", "targety", "transform", "text-anchor", "text-decoration", "text-rendering", "textlength", "type", "u1", "u2", "unicode", "values", "viewbox", "visibility", "vert-adv-y", "vert-origin-x", "vert-origin-y", "width", "word-spacing", "wrap", "writing-mode", "xchannelselector", "ychannelselector", "x", "x1", "x2", "xmlns", "y", "y1", "y2", "z", "zoomandpan", ]
          , h = ["accent", "accentunder", "align", "bevelled", "close", "columnsalign", "columnlines", "columnspan", "denomalign", "depth", "dir", "display", "displaystyle", "fence", "frame", "height", "href", "id", "largeop", "length", "linethickness", "lspace", "lquote", "mathbackground", "mathcolor", "mathsize", "mathvariant", "maxsize", "minsize", "movablelimits", "notation", "numalign", "open", "rowalign", "rowlines", "rowspacing", "rowspan", "rspace", "rquote", "scriptlevel", "scriptminsize", "scriptsizemultiplier", "selection", "separator", "separators", "stretchy", "subscriptshift", "supscriptshift", "symmetric", "voffset", "width", "xmlns", ]
          , d = ["xlink:href", "xml:id", "xlink:title", "xml:space", "xmlns:xlink"]
          , p = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(c) {
            return typeof c;
        }
        : function(c) {
            return c && "function" == typeof Symbol && c.constructor === Symbol && c !== Symbol.prototype ? "symbol" : typeof c;
        }
          , z = function() {
            return "undefined" == typeof window ? null : window;
        }
          , u = a();
        return u;
    });
}
, ]);

var keyindex, macmenulinks, keyindex = 0;

// bof: JavaScript Document begins here
/**
 * Configure menu interactions
 */
const setup_mcmenuClick = () => {
    const mcmenu = document.querySelector("#mcmenu");

    mcmenu?.addEventListener("click", (event) => {
        const header = document.querySelector("header");
        header.classList.contains("menu-active") ? collapseMenu(event) : expandMenu(event);
    }
    );
}
;

/**
 * Expand the menu
 *
 * @param object event - The event object
 */
const expandMenu = (event) => {
    event.preventDefault();

    closeSearch(event);
    // Close the search if it is open

    let el;

    // close_search(); // Close search, it might be open

    el = document.querySelector("#mcmaster-header");
    el.classList.add("menu-active");
    // add search-active class to header class

    el = document.querySelector("#mcmaster-nav a:first-child");
    el.focus();
    // set focus to first link in nav

    el = document.querySelector("#mcmenu");
    // Set aria-expanded to true
    el.setAttribute("aria-expanded", "true");

    el = document.querySelector("#mcmaster-nav");
    // Show the Mac menu and set overflow to scroll
    el.style.display = "block";
    el.style.overflowY = "scroll";

    el = document.querySelector("body");
    // Add no scroll to body so menu stays intact
    el.classList.add("noscroll");

    // jQuery("body a,button,select,input,textarea,.hero-carousel").not("#navLinks a,#mcmaster-nav a").attr("tabindex", "-1"); // remove tabbing on body items
    // Select all anchor tags except for the ones in the menus
    let elList = "body a:not(#navLinks a, #mcmaster-nav a.collapsed), ";
    // Select all other elements that can be tabbed to
    elList += "button, select, input, textarea";
    el = document.querySelectorAll(elList);
    el.forEach( (e) => {
        // Turn off tabbing for other focusable items
        e.setAttribute("tabindex", "-1");
    }
    );

    // jQuery("#mcmaster-nav a").attr("tabindex", "0"); // add tabbing to menu items
    el = document.querySelectorAll("#mcmaster-nav a.collapsed, #navLinks a");
    // Set tabindex to 0
    el.forEach( (e) => {
        // Turn on tabbing for menu items
        e.setAttribute("tabindex", "0");
    }
    );
}
;

/**
 * Collapse the menu
 *
 * @param object event - event object
 */
const collapseMenu = (event) => {
    // event.preventDefault();

    let elList, el;

    elList = "#mcmenu, #mcmaster-nav li a.collapsed, #mcmaster-nav li ul";
    el = document.querySelectorAll(elList);
    // Set aria-expanded to false
    el.forEach( (e) => {
        let ariaExpanded = 'false';
        // If element is an anchor tag, and parent is #mcmaster-nav, console.log it
        if (e.tagName === "A" && e.closest("#mcmaster-nav")) {
            if (e.getAttribute("aria-expanded") === "true") {
                ariaExpanded = 'true';
                // console.log(e);
            }
        }
        e.setAttribute("aria-expanded", ariaExpanded);
    }
    );

    el = document.querySelector("#mcmaster-nav li ul");
    // Set height to 0px
    el.style.height = "0px";

    el = document.querySelector("body");
    // Remove no scroll from body so we can scroll down once menu is closed
    el.classList.remove("noscroll");

    // elList = elList = "body a, button, select, input, textarea, .hero-carousel :not(#navLinks a, #mcmaster-nav a)";
    // Select all anchor tags except for the ones in the menus
    elList = "body a:not(#navLinks a, #mcmaster-nav a.collapsed), ";
    // Select all other elements that can be tabbed to
    elList += "button, select, input, textarea";
    // add tabbing back to the body items
    el = document.querySelectorAll(elList);
    el.forEach( (e) => {
        e.setAttribute("tabindex", "0");
    }
    );

    // Select all anchor tags in the menus
    elList = "#mcmaster-nav a.collapsed, #mcmaster-nav li a";
    // Set tabindex to no tabbing
    el = document.querySelectorAll(elList);
    el.forEach( (e) => {
        e.setAttribute("tabindex", "-1");
    }
    );

    // remove menu-active class from header class
    el = document.querySelector("#mcmaster-header");
    el.classList.remove("menu-active");

    // el = document.querySelector("#mcmenu"); // Set focus on menu button
    // el.focus();

    keyindex = 0;
    // keyindex from above
}
;

/**
 * Configure the search interactions
 */
const setup_mcmasterSearchClick = () => {
    const mcmasterSearch = document.querySelector("#mcmaster-search");

    mcmasterSearch?.addEventListener("click", (event) => {
        const header = document.querySelector("header");
        header.classList.contains("search-active") ? closeSearch(event) : openSearch(event);
    }
    );
}
;

/**
 * Open the search
 * @param object event - The event object
 */
const openSearch = (event) => {
    event.preventDefault();

    collapseMenu(event);
    // Close menu, it might be open

    let elList, el;
    // jQuery("body").addClass("noscroll"); // Add no scroll to body so menu stays intact
    el = document.querySelector("body");
    el.classList.add("noscroll");

    // add search-active class to header class
    el = document.querySelector("#mcmaster-header");
    el.classList.add("search-active");

    // add role as dialog to overlay
    el = document.querySelector("#mcmaster-search-overlay");
    el.setAttribute("role", "dialog");

    // Display the overlay
    el = document.querySelector("#mcmaster-search-overlay");
    el.style.display = "block";

    // Select all anchor tags except for those in the nav menu and the search overlay
    elList = "body a";
    elList += ":not(";
    elList += "#mcmaster-search-overlay a, #navLinks a, #mcmaster-nav a, #search-input input, #mcmaster-search-overlay button";
    elList += ")";
    elList += ", select, input, textarea";

    // Set tabindex to "0" for all elements in the overlay
    el = document.querySelectorAll(elList);
    // move tabbing back to the body items
    el.forEach( (e) => {
        e.setAttribute("tabindex", "0");
    }
    );

    // jQuery("#keyword").focus(); focus on the search textbox
    el = document.querySelector("#keyword");
    el.focus();
}
;

/**
 * Collapse the search
 *
 * @param object event - The event object
 */
const closeSearch = (event) => {
    event.preventDefault();

    let elList, el;

    // Hide the overlay if it's open
    el = document.querySelector("#mcmaster-search-overlay");
    el.style.display = "none";

    // Remove no scroll from body so we can scroll down once menu is closed
    el = document.querySelector("body");
    el.classList.remove("noscroll");

    // remove search-active class from header class
    el = document.querySelector("#mcmaster-header");
    el.classList.remove("search-active");

    // Set tabindex to "-1" for all elements for all elements in the overlay
    elList = "body a";
    elList += ":not(";
    elList += "#mcmaster-search-overlay a, #navLinks a, #mcmaster-nav a, #search-input input, #mcmaster-search-overlay button";
    elList += ")";
    elList += ", select, input, textarea";

    // add tabbing back to the body items
    el = document.querySelectorAll(elList);
    el.forEach( (e) => {
        e.setAttribute("tabindex", "-1");
    }
    );
}
;

/**
 *  Configure the sub-menu interactions
 */
const setup_submenuClick = () => {
    const subMenu = document.querySelector("#mcmaster-nav");
    // Set up event listeners for the sub-menu
    subMenu?.addEventListener("click", (event) => {
        subMenuClick(event);
    }
    );
}
;

/**
 * Process submenu click
 *
 * @param object event - The event object
 */
const subMenuClick = (event) => {
    const el = event.target;
    const dparent = event.target.getAttribute("data-dparent");
    const dParentEl = document.querySelector(`#${dparent}`);
    const parentEl = el.parentElement;
    let elList, els;

    keyindex = Array.from(parentEl.parentElement.children).indexOf(parentEl);
    if (dParentEl?.getAttribute('aria-expanded') === "false") {
        // Now go into this if the item is not active
        el.setAttribute("aria-expanded", "true");
        // Set aria-expanded to true
        elList = "#mcmaster-nav .collapsed";
        // Set aria-expanded  for all anchors except for the clicked item to false in case something is open.
        els = document.querySelectorAll(elList);
        els.forEach( (e) => {
            if (e !== el) {
                e.setAttribute("aria-expanded", "false");
            }
        }
        );
        elList = "#mcmaster-nav li ul";
        // Set aria-expanded to false in case something is open.
        els = document.querySelectorAll(elList);
        els.forEach( (e) => {
            e.setAttribute("aria-expanded", "false");
            e.style.height = "0px";
        }
        );
        dParentEl.style.height = "100%";
        // Expand the ul submenu to 100%
        elList = `#${dparent} a`;
        // Set tabindex to 0 on all anchors under the ul in the menu
        els = document.querySelectorAll(elList);
        els.forEach( (e) => {
            e.setAttribute("tabindex", "0");
        }
        );
        dParentEl.setAttribute("aria-expanded", "true");
        // Set aria-expanded to true
    } else {
        el.setAttribute("aria-expanded", "false");
        // Set aria-expanded to false
        if (dParentEl?.hasOwnProperty("style")) {
            dParentEl.style.height = "0px";
            // Collapse the ul submenu by adding height 0px to the style
        }
        elList = `#${dparent} a`;
        // Set tabindex to -1 on all anchors under the ul in the menu
        els = document.querySelectorAll(elList);
        els.forEach( (e) => {
            e.setAttribute("tabindex", "-1");
        }
        );
        dParentEl?.setAttribute("aria-expanded", "false");
        // Set aria-expanded to false on current ul
    }
}
;

const setup_mcmasterNavKeyUp = () => {
    // Set up event listeners for keyup on the menu and search overlay
    window.addEventListener("keyup", (event) => {
        // trap the esacpe key
        if (event.key === "Escape") {
            const mcmenu = document.querySelector("#mcmenu");
            const searchOverlay = document.querySelector("#mcmaster-search-overlay");
            const mcsearch = document.querySelector("#mcmaster-search");

            if (mcmenu?.getAttribute("aria-expanded") === "true") {
                // Log the active element
                // const el = document.querySelectorAll("#mcmaster-nav a[tabindex='0']");
                const el = document.querySelector('#mcmaster-nav a[aria-expanded="true"]');
                el?.click();
                collapseMenu(event);
                mcmenu.focus();
            } else if (searchOverlay?.style.display === "block") {
                // collapseMenu(event);
                closeSearch(event);
                mcsearch.focus();
            }
        } else {
            mcmasterKeyNav(event);
        }
    }
    );
}
;

/**
 * Process keydown event
 *
 * @param object event - The event object
 */
const mcmasterKeyNav = (event) => {
    const el = event.target;
    // find items that are currently tabbable in the menu
    const macmenulinks = document.querySelectorAll('#mcmaster-nav a[tabindex="0"]');
    // Find the last child in the menu
    const lastChildParent = document.querySelector("#mcmaster-nav > li:last-child a");
    const lastChildEl = document.querySelector("#mcmaster-nav > li:last-child > ul > li:last-child a");
    // Detect the arrow left key
    const onlastSubItemKeyDown = (event) => {
        // Detect the Tab key
        if (event.key === "Tab") {
            // Focus on the first element in the menu
            macmenulinks[0].focus();
            // Collapse the group by simulating a click
            lastChildParent?.click();
            event.preventDefault();
        }
    }
    ;

    // Set the active element
    const activeEl = document.activeElement;

    // If the active element is not in the menu, return
    if (!activeEl?.closest("#mcmaster-nav")) {
        return;
    }

    const activeElParent = activeEl.parentElement;
    const subMenuactiveEl = activeEl.parentElement?.parentElement?.previousElementSibling;
    // Prevent default
    event.preventDefault();
    try {
        // Get the index of the active element using the grand parent of the active anchor element
        if (subMenuactiveEl?.tagName === "A") {
            // Are we in a submenu?
            // Detect the arrow left key
            if (event.key === "ArrowLeft") {
                subMenuactiveEl.click();
                subMenuactiveEl.focus();
                return;
            } else if (event.key === "ArrowUp") {
                keyindex = Array.from(activeElParent.parentElement.children).indexOf(activeElParent);
                keyindex = keyindex > 0 ? --keyindex : 0;
                // Focus sub menu child items
                activeElParent.parentElement?.children[keyindex]?.children[0].focus();
            } else if (event.key === "ArrowDown") {
                const childCount = activeElParent.parentElement.children.length;
                keyindex = Array.from(activeElParent.parentElement.children).indexOf(activeElParent);
                keyindex = keyindex < childCount - 1 ? ++keyindex : keyindex;
                // Focus sub menu child items
                activeElParent.parentElement?.children[keyindex]?.children[0].focus();
            } else if (event.key === "Tab") {
                // If the Shift key is pressed
                if (!event.shiftKey) {
                    // If the active element is the last element in the menu
                    if (activeEl === lastChildEl) {
                        lastChildEl.removeEventListener("keydown", onlastSubItemKeyDown);
                        lastChildEl.addEventListener("keydown", onlastSubItemKeyDown);
                    }
                    // Check if the active element is the last element in the submenu, and has a listener for keydown
                }
            }
        } else {
            if (activeElParent?.parentElement) {
                // Detect the arrow right key or arrow left key
                if (event.key === "ArrowRight" || event.key === 'ArrowLeft') {
                    // Expand submenu if it exists
                    if ((activeElParent?.parentElement?.tagName === 'UL') && (activeElParent?.parentElement?.id === 'mcmaster-nav')) {
                        // Simulate enter key press
                        activeEl.click();
                    }
                } else if (event.key === "ArrowUp") {
                    keyindex = Array.from(activeElParent.parentElement.children).indexOf(activeElParent);
                    keyindex = keyindex > 0 ? --keyindex : 0;
                    macmenulinks[keyindex]?.focus();
                } else if (event.key === "ArrowDown") {
                    keyindex = 0;
                    // If the active element is not the hamburger menu element
                    if (activeElParent.id !== "navLinks") {
                        keyindex = Array.from(activeElParent.parentElement.children).indexOf(activeElParent);
                        keyindex = keyindex < (macmenulinks.length - 1) ? ++keyindex : keyindex;
                    }
                    macmenulinks[keyindex]?.focus();
                }
            }
        }
    } catch (error) {
        console.error(error);
    }
}
;

/**
 * Configure the search clearance interactions
 */
const setup_clearSearchClick = () => {
    const searchInput = document.querySelector("#clearSearch");
    // Add event listener to the search input
    searchInput?.addEventListener("click", (event) => {
        const el = document.querySelector("#keyword");
        el.value = "";
        el.focus();
    }
    );
}
;

/**
 * Configure Skip Link interactions
 */
const setup_skipLinkNavClick = () => {
    const skipLinkNav = document.querySelector("a#mcmenu");
    // Add event listener to the skip link
    skipLinkNav?.addEventListener("click", (event) => {
        setTimeout( () => {
            const el = document.querySelector("#mcmenu");
            el?.focus();
        }
        , 100);
    }
    );
}
;

/**
 * Capture focus event for the search buttons
 * to highlight them when they are focused
 */
const setup_focusTrap = () => {
    const btnGroup = document.querySelector(".btn-group");
    // Set up event listener for focus on the menu and search overlay
    btnGroup?.addEventListener("focus", (event) => {
        // Set the focus style on the focused element
        event.target.style = "box-shadow: 0 0 0 0.2rem rgb(23 162 184 / 50%);";
    }
    , true);
}

/**
 * Capture blur event for the search buttons set them back to
 * default colours when they lose focus
 */
const setup_blurTrap = () => {
    const btnGroup = document.querySelector(".btn-group");
    const search = document.querySelector("#mcmaster-search");
    const menu = document.querySelector("#mcmenu");
    const header = document.querySelector("#mcmaster-header");
    // Set up event listener for blur on the menu and search overlay
    btnGroup?.addEventListener("blur", (event) => {
        // Set the blurred style on the blurred element
        event.target.style = "box-shadow: unset;";
    }
    , true);
    // Set up event listener for blur on the menu
    menu?.addEventListener("keydown", (event) => {
        // Checks if the Tab key is pressed.
        const isTabPressed = event.key === 'Tab' || event.keyCode === 9;
        if (!isTabPressed) {
            return;
        }
        // Set focus to the first visible anchor tag in the menu
        if (header?.classList.contains("menu-active")) {
            // Set the focus to the first visible anchor tag in the menu
            const firstVisible = document.querySelector("#mcmaster-nav a[tabindex='0']");
            firstVisible?.focus();
            event.preventDefault();
        }
    }
    );
    // Set up event listener for blur on the search button
    search?.addEventListener("blur", (event) => {
        // Close the menu when it loses focus
        if (event.relatedTarget !== menu) {
            collapseMenu(event);
        }
    }
    , true);
}

/**
 * Sets up the blur trap for the search overlay.
 * When the last anchor element inside the search overlay loses focus,
 * it will bring focus back to the keyword element.
 */
const setup_blurTrapSearch = () => {
    const search = document.querySelector("#mcmaster-search-overlay");
    // Get all anchor elements inside the search overlay
    const anchorChildren = Array.from(search?.querySelectorAll("a"));
    // Get the last anchor element
    const lastSearchChild = anchorChildren[anchorChildren?.length - 1];
    // Set up event listener for blur on the last anchor element
    lastSearchChild?.addEventListener("blur", (event) => {
        // Go back to the keyword element
        search.querySelector("#keyword").focus();
    }
    , true);
}

/**
 * Sets up the blur trap menu functionality.
 */
const setup_blurTrapMenu = () => {
    const menuList = {
        first: document.querySelector("#mcmaster-nav > li:first-child a"),
        last: document.querySelector("#mcmaster-nav > li:last-child a")
    };
    // Set up event listener for blur on the last anchor element
    menuList.last?.addEventListener("keydown", (event) => {
        //  if the tab key is pressed without the shift key, et focus to the first element
        const subMenu = document.querySelector("#mcmaster-nav > li:last-child ul");
        const subMenuExpanded = subMenu?.getAttribute("aria-expanded") === "true";
        if ((event.key === 'Tab' && !event.shiftKey) && !subMenuExpanded) {
            menuList.first?.focus();
            event.preventDefault();
        }
    }
    , true);
}

/**
 * Sets up the carousel tabbing functionality.
 */
const setup_carouselTabbing = () => {
    const carousel = document.querySelector(".hero-carousel");
    // If there is no carousel on the page we return
    if (!carousel) {
        return;
    }
    // Turn off tabbing fo the carousel
    carousel?.setAttribute("tabindex", "-1");

    // Get all focusable items in the carousel
    let focusable = 'a[href], area[href], input:not([disabled]), ';
    focusable += 'select:not([disabled]), textarea:not([disabled]), button:not([disabled]), ';
    focusable += 'iframe, object, embed, [tabindex="0"], [contenteditable]';
    const items = Array.from(carousel?.querySelectorAll(focusable));
    // Turn off tabbing for all items
    items?.forEach( (item) => {
        item.setAttribute("tabindex", "-1");
    }
    );

    // Turn on tabbing for the volume and play/pause buttons
    const controlButtons = Array.from(carousel?.querySelectorAll('.video-controls button'));
    controlButtons?.forEach( (button) => {
        button.setAttribute("tabindex", "0");
    }
    );

    // Turn on tabbing for the carousel CTA buttons only
    const ctaBtns = Array.from(carousel?.querySelectorAll('.btn'));
    ctaBtns?.forEach( (button) => {
        button.setAttribute("tabindex", "0");
    }
    );

    // Turn on tabbing for the carousel navigation buttons only
    const navButtons = Array.from(carousel?.querySelectorAll('.flickity-prev-next-button'));
    navButtons?.forEach( (button) => {
        button.setAttribute("tabindex", "0");
    }
    );
}

/**
 * Sets up the event listener for the modal show event and focuses on the first focusable element in the modal.
 */
const setup_onModalShow = ($) => {
    const modalTriggers = document.querySelectorAll('[href^="#modal"], [data-target^="#modal"]');
    // Set up event listener for the click event on the modal triggers (anchor elements)
    modalTriggers?.forEach( (trigger) => {
        trigger.addEventListener('click', function(event) {
            // Prevent the default action for the click event
            event.preventDefault();
            // Get the value of the href attribute without the leading '#' character
            const attr = this.getAttribute('href');
            // Set the modalId to the data-target attribute if the href attribute is '#'
            const modalId = (attr === '#!' || attr === '#') ? this.getAttribute('data-target') : attr;
            // Get the modal element with id equal to the modalId constant
            const modal = document.querySelector(modalId);
            // Check if the modal exists and is not null
            if (modal) {
                // Set up variables for the first focusable element, focusables, and the last focusable element
                const selector = 'a[href], button:not([disabled]), input:not([disabled]), ' + 'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
                const firstFocusable = modal.querySelector(selector);
                const focusables = modal.querySelectorAll(selector);
                const lastFocusable = focusables[focusables.length - 1];
                let shiftKeyPressed = false;

                const allFocusableElements = document.querySelectorAll(selector);
                const originalTabindex = new Map();
                allFocusableElements.forEach(element => {
                    if (!modal.contains(element)) {
                        originalTabindex.set(element, element.getAttribute('tabindex'));
                        element.setAttribute('tabindex', '-1');
                    }
                }
                );

                // Restore original tabindex values when the modal is hidden
                $(modal).on('hidden.bs.modal', function(event) {
                    originalTabindex.forEach( (value, element) => {
                        if (value === null) {
                            element.removeAttribute('tabindex');
                        } else {
                            element.setAttribute('tabindex', value);
                        }
                    }
                    );
                });

                // Attach the 'keydown event' for the modal, and detect the shift key
                // Note: The 'keydown event' occurs before the 'blur' event so we set the shiftKeyPressed variable here
                modal?.addEventListener('keydown', function(event) {
                    // Set the shiftKeyPressed variable to true if the user holds down the shift and tab keys
                    shiftKeyPressed = (event.shiftKey && event.key === 'Tab');
                    // Get the currently focused element
                    const activeElement = document.activeElement;

                    // Check if the Tab key is pressed
                    if (event.key === 'Tab') {
                        // If the focus is on the last focusable element and the Shift key is not pressed
                        if (!shiftKeyPressed && activeElement === lastFocusable) {
                            event.preventDefault();
                            firstFocusable?.focus();
                        }// If the focus is on the first focusable element and the Shift key is pressed
                        else if (shiftKeyPressed && activeElement === firstFocusable) {
                            event.preventDefault();
                            lastFocusable?.focus();
                        }
                    }

                    // Check if the Escape or Enter key is pressed
                    if (event.key === 'Escape' || event.key === 'Enter') {
                        // Hide the modal
                        $(modalId).modal('hide').on('hidden.bs.modal', function() {
                            $(modalId).modal('dispose');
                        });
                    }
                });
                // Show the modal
                $(modalId).modal('show').on('shown.bs.modal', function(event) {
                    // Set focus to the last focusable element in the modal which is genreally
                    // the Close button
                    lastFocusable?.focus();
                });
            }
        });
    }
    );
}

/**
 * Sets up the tabindex for people cards and adds keyboard navigation enhancements.
 *
 * This function selects all div elements within the #people-row element and processes each card.
 * For each card, it sets the tabindex attribute to 0 for all anchor links with the classes
 * 'list-group-item' or 'btn-info'. Additionally, it adds event listeners to the second last and
 * last anchor links to change their background color when the Tab key is pressed.
 *
 * Event Listeners:
 * - Second last link: Changes the background color of the [last link] to yellow when Tab is pressed.
 * - Last link: Restores the original background color when Tab is pressed.
 */
const setup_peopleTabIndex = () => {
    const peopleCards = document.querySelectorAll('#people-row > div');
    peopleCards?.forEach( (card) => {
        // Get all anchor links on the current card element including the 'more information' link
        const links = card.querySelectorAll('.btn-info');
        // Set up events for each link
        links?.forEach( (link) => {
            // Set the focus style on the focused element
            link.addEventListener('focus', (event) => {
                event.target.classList.add('btn-info-focus');
            }
            );
            // Remove the focus style on the blurred element
            link.addEventListener('blur', (event) => {
                event.target.classList.remove('btn-info-focus');
            }
            );
        }
        );
    }
    );
}
;

// IIFE - Immediately Invoked Function Expression
( ($) => {
    window.addEventListener("load", () => {
        setup_mcmenuClick();
        setup_mcmasterSearchClick();
        setup_submenuClick();
        setup_clearSearchClick();
        setup_skipLinkNavClick();
        setup_mcmasterNavKeyUp();
        setup_focusTrap();
        setup_blurTrap();
        setup_blurTrapSearch();
        setup_blurTrapMenu();
        setup_carouselTabbing();
        setup_onModalShow($);
        setup_peopleTabIndex();
    }
    );
}
)(jQuery);
// eof: JavaScript Document ends here

// Hussein Mukri - Student Affairs Tech Team
// Let's fix some of the menu and search overlay issues with accessiblity
// Revised: 2021-03-04
// Revised: 2021-11-11 - Added focus trap for the search buttons / Re-added setRoboto() method
