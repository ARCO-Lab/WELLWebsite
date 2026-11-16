// The one way the page writes its link's query string (utils/chartWindow searchWithWindow, utils/selectionLink), so
// ?from=&to= and ?groups=&creeks= never rewrite each other's parameters in a different encoding.

/** "?a=1&b=x,y" from the parameters ("" when there are none). Commas stay as they are: they are fine in a query
 *  string and easier to read ("groups=gauges,weather", not "groups=gauges%2Cweather"). */
export function searchString(q: URLSearchParams): string {
  const s = q.toString().replace(/%2C/gi, ",");
  return s ? `?${s}` : "";
}
