<?php
// The interactive "Check my CSV format" tool for the Sampling Data Upload Guide.
//
// This stays developer-owned PHP, not editable blocks: it posts the chosen file to the dashboard's
// /api/samples/validate endpoint (the real import validator) and refreshes its reference lists from
// /api/samples/format, driven by js/sampling-check.js and styled by css/sampling-check.css. The guide
// PROSE around it is editable blocks; this widget is placed with the [well_sampling_checker] shortcode
// (see inc/shortcodes.php) and kept in code so it stays functional.
//
// The heading keeps its id="sampling-checker" so the "Check my CSV format" link earlier in the guide
// still jumps here.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

$dashboard_url = rtrim(getenv('DASHBOARD_URL') ?: 'https://welldash.mcmaster.ca', '/');
$validate_url  = $dashboard_url . '/api/samples/validate';
$format_url    = $dashboard_url . '/api/samples/format';

wp_enqueue_style(
  'well-sampling-check',
  get_template_directory_uri() . '/css/sampling-check.css',
  array(),
  well_asset_version('/css/sampling-check.css')
);
wp_enqueue_script(
  'well-sampling-check',
  get_template_directory_uri() . '/js/sampling-check.js',
  array(),
  well_asset_version('/js/sampling-check.js'),
  true
);
?>
<h2 id="sampling-checker">Check my CSV format</h2>
<p>Paste the contents of your CSV, or choose the file, then press <strong>Check</strong>. Nothing is uploaded
   or saved anywhere. This only reads your file and tells you whether it would import. It runs the very same
   check the weekly import uses, so a pass here means a pass there.</p>

<div class="sampling-checker"
     data-validate-url="<?php echo esc_url($validate_url); ?>"
     data-format-url="<?php echo esc_url($format_url); ?>">
  <div class="form-group">
    <label for="sampling-file"><strong>Choose a CSV file</strong></label>
    <input type="file" id="sampling-file" accept=".csv,text/csv" class="form-control-file">
  </div>
  <div class="form-group">
    <label for="sampling-text"><strong>…or paste the CSV text</strong></label>
    <textarea id="sampling-text" class="form-control" rows="8"
              placeholder="date,time,site,parameter,value,unit,...&#10;2026-05-06,09:40,Falkirk Forest,E. coli,48,CFU/100 mL,..."></textarea>
  </div>
  <div class="sampling-checker__actions">
    <button type="button" id="sampling-check-btn" class="btn btn-primary">Check</button>
    <button type="button" id="sampling-clear-btn" class="btn btn-outline-secondary">Clear</button>
  </div>
  <div id="sampling-result" class="sampling-result" role="status" aria-live="polite"></div>
</div>

<noscript>
  <div class="alert-box alert-box--info mt-3">The live checker needs JavaScript. You can still upload your
    file to Borealis: the weekly import will check it and the WELL team will tell you if anything needs
    fixing.</div>
</noscript>
