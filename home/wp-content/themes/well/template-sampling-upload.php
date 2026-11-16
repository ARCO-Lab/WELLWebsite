<?php
/**
 * Template Name: Sampling Data Upload Guide
 *
 * A link-only help page for researchers who have creek sampling data to contribute. It explains, in plain language,
 * how the data pipeline works and how to format and upload a CSV so it imports without errors, and it embeds a
 * "Check my CSV format" tool.
 *
 * The tool does NOT keep a second copy of the format rules: it posts the file to the dashboard's
 * /api/samples/validate, which runs the real import validator (dashboard/backend/app/utils/sampling_csv.py), so its
 * verdict is exactly what the weekly Borealis import would say. The reference tables below are a static fallback
 * that js/sampling-check.js refreshes from /api/samples/format (the same lists), so they can't drift either.
 *
 * This template is assigned to a Page with an unlisted slug, kept out of the nav menus, and marked noindex by
 * well_sampling_upload_noindex() in functions.php, so the page is reachable only by its link.
 *
 * Screenshots: the step boxes below hold captioned placeholders. Drop real screenshots into
 * img/media/ (e.g. sampling-borealis-upload.webp) and replace the matching placeholder <div> with an <img>, or add
 * them through the media library. Do not paste branded Borealis/McMaster screenshots you do not have the right to
 * publish.
 */
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

// The dashboard's origin, where the checker endpoints live. Same resolution as page-dashboard.php.
$dashboard_url   = getenv('DASHBOARD_URL') ?: 'https://welldash.mcmaster.ca';
$dashboard_url   = rtrim($dashboard_url, '/');
$validate_url    = $dashboard_url . '/api/samples/validate';
$format_url      = $dashboard_url . '/api/samples/format';
$template_url    = $dashboard_url . '/api/sampling-template';
$borealis_url    = 'https://borealisdata.ca/dataverse/WELL';

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

get_header();
?>

<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-2">Sampling data upload — researcher guide</h1>
        <p class="lead mb-0">How to format and upload your creek sampling results so they appear on the WELL dashboard, plus a tool to check your file before you send it.</p>
      </div>
    </div>
  </div>
</header>

<main id="site-content">
  <section class="section-padding">
    <div class="container sampling-guide">

      <!-- Intro / how the pipeline works -->
      <div class="row">
        <div class="col-lg-8">
          <h2>How your data reaches the dashboard</h2>
          <p>When you have sampling results from the Ancaster Creek watershed, you share them as a spreadsheet (a
             CSV file) by uploading it to our <strong>Borealis</strong> data repository. From there everything is
             automatic:</p>
          <ol>
            <li>You upload your CSV to the <em>Ancaster Watershed Sampling Uploads</em> dataset on Borealis.</li>
            <li>Once a week, WELL downloads any new files from that dataset.</li>
            <li>Each file is <strong>checked against the standard format</strong>. If it passes, every reading is
                imported automatically.</li>
            <li>Your readings appear on the dashboard's <strong>Ancaster Watershed</strong> tab, where anyone can
                view and download them.</li>
          </ol>
          <p>If a file does <strong>not</strong> match the format, <strong>nothing from it is imported</strong> and
             the WELL team is alerted to take a look. Your data is never half-imported — so it is worth getting the
             format right, and that is what this page is for.</p>
        </div>
        <div class="col-lg-4">
          <?php
          // Original, simple pipeline diagram (not a screenshot). Decorative detail is in the text above, so the
          // SVG gets a short title/desc for screen readers.
          ?>
          <figure class="sampling-pipeline" aria-hidden="false">
            <svg viewBox="0 0 220 300" width="100%" height="auto" role="img"
                 aria-labelledby="pipe-title pipe-desc">
              <title id="pipe-title">The sampling data pipeline</title>
              <desc id="pipe-desc">Your CSV goes to Borealis, is downloaded and checked weekly, then imported into the dashboard.</desc>
              <g font-family="Poppins, sans-serif" font-size="12" text-anchor="middle">
                <rect x="20" y="10"  width="180" height="46" rx="8" fill="#7a003c"></rect>
                <text x="110" y="31" fill="#fff">Your CSV file</text>
                <text x="110" y="47" fill="#fdbf57" font-size="10">(from the template)</text>
                <line x1="110" y1="56" x2="110" y2="78" stroke="#495965" stroke-width="2" marker-end="url(#arrow)"></line>
                <rect x="20" y="80" width="180" height="46" rx="8" fill="#fff" stroke="#7a003c" stroke-width="2"></rect>
                <text x="110" y="101" fill="#7a003c">Upload to Borealis</text>
                <text x="110" y="117" fill="#495965" font-size="10">Sampling Uploads dataset</text>
                <line x1="110" y1="126" x2="110" y2="148" stroke="#495965" stroke-width="2" marker-end="url(#arrow)"></line>
                <rect x="20" y="150" width="180" height="46" rx="8" fill="#fff" stroke="#7a003c" stroke-width="2"></rect>
                <text x="110" y="171" fill="#7a003c">Weekly download</text>
                <text x="110" y="187" fill="#495965" font-size="10">checked &amp; validated</text>
                <line x1="110" y1="196" x2="110" y2="218" stroke="#495965" stroke-width="2" marker-end="url(#arrow)"></line>
                <rect x="20" y="220" width="180" height="46" rx="8" fill="#7a003c"></rect>
                <text x="110" y="241" fill="#fff">Dashboard</text>
                <text x="110" y="257" fill="#fdbf57" font-size="10">Ancaster Watershed tab</text>
              </g>
              <defs>
                <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
                  <path d="M0,0 L8,4 L0,8 Z" fill="#495965"></path>
                </marker>
              </defs>
            </svg>
            <figcaption>How a sampling file travels from your computer to the dashboard.</figcaption>
          </figure>
        </div>
      </div>

      <hr class="my-5">

      <!-- Step by step -->
      <h2>Step by step</h2>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">1</span> Download the template</h3>
        <p>Start from the blank template — it already has the correct column headings and a few example rows:</p>
        <p>
          <a class="btn btn-primary" style="background-color:#fdbf57;color:#000;border-color:#fdbf57;"
             href="<?php echo esc_url($template_url); ?>">Download the CSV template</a>
        </p>
        <p class="text-muted">Open it in Excel, Google Sheets or Numbers. Keep the heading row exactly as it is.</p>
        <div class="sampling-shot" role="img" aria-label="Screenshot placeholder: the template open in a spreadsheet">
          <span>Screenshot placeholder — the template open in a spreadsheet. (Add your own image here.)</span>
        </div>
      </div>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">2</span> Fill in your readings</h3>
        <p>The golden rule: <strong>one reading per row</strong>. If you measured nine things at one site on one
           visit, that is nine rows — one per parameter. Fill in these columns:</p>

        <h4 class="h5 mt-4">Required in every row</h4>
        <ul class="sampling-cols" id="required-columns">
          <li><code>date</code> — the sampling date as <code>YYYY-MM-DD</code> (for example <code>2026-05-06</code>).</li>
          <li><code>site</code> — one of the sites in the table below.</li>
          <li><code>parameter</code> — one of the parameters in the table below.</li>
          <li><code>value</code> — a plain number (for example <code>1295</code> or <code>0.015</code>).</li>
          <li><code>unit</code> — the parameter's unit, exactly as listed below.</li>
        </ul>

        <h4 class="h5 mt-4">Optional (fill in if you have them)</h4>
        <ul class="sampling-cols" id="optional-columns">
          <li><code>time</code> — time of sampling in 24-hour <code>HH:MM</code> (for example <code>14:05</code>), local Hamilton time.</li>
          <li><code>creek</code> — the creek's name (a cross-check that you picked the right site).</li>
          <li><code>below_detection</code> — <code>true</code> if the value was below the detection limit.</li>
          <li><code>qc_flag</code> — <code>ok</code>, <code>suspect</code> or <code>rejected</code>.</li>
          <li><code>sampler</code>, <code>method</code>, <code>notes</code> — anything else worth recording.</li>
        </ul>

        <div class="alert-box alert-box--info">
          <strong>Formatting that trips people up:</strong>
          <ul class="mb-0">
            <li><strong>Dates must be <code>YYYY-MM-DD</code>.</strong> A date like <code>05/06/2026</code> is rejected because it could mean 5 June or 6 May — the system never guesses.</li>
            <li><strong>Values are plain numbers:</strong> no commas for thousands, no units in the cell. Put the unit in the <code>unit</code> column.</li>
            <li><strong>Below the detection limit?</strong> Write the limit with a <code>&lt;</code> in front, e.g. <code>&lt;0.01</code>.</li>
            <li><strong>Didn't measure something?</strong> Leave that row out, or leave <code>value</code> empty. Never write <code>0</code> for "not measured".</li>
            <li><strong>Save as CSV UTF-8.</strong> In Excel: <em>File → Save As → CSV UTF-8 (Comma delimited)</em>.</li>
          </ul>
        </div>

        <h4 class="h5 mt-4">Sites</h4>
        <p>Use the site's name, its number, or both (for example <code>Falkirk Forest</code>, <code>1</code>, or
           <code>#1 Falkirk Forest</code>). Spelling matters; capitals and extra spaces do not.</p>
        <div class="table-responsive">
          <table class="table table-sm sampling-ref" id="sites-table">
            <thead><tr><th>Site number</th><th>Name</th><th>Creek</th></tr></thead>
            <tbody>
              <tr><td>1</td><td>Falkirk Forest</td><td>Tiffany Creek</td></tr>
              <tr><td>2</td><td>Maple Lane Pk</td><td>Ancaster Creek</td></tr>
              <tr><td>3</td><td>Jerseyville Rd</td><td>Sulphur Creek</td></tr>
              <tr><td>4</td><td>Sulphur Springs</td><td>Sulphur Creek</td></tr>
              <tr><td>5</td><td>Sherman Falls</td><td>Ancaster Creek</td></tr>
              <tr><td>6</td><td>Tiffany Falls</td><td>Tiffany Creek</td></tr>
              <tr><td>8</td><td>Osler Dr</td><td>Coldwater Creek</td></tr>
              <tr><td>9</td><td>McMaster Lot P</td><td>Coldwater Creek</td></tr>
              <tr><td>10</td><td>Cootes Dr</td><td>Spencer's Creek</td></tr>
            </tbody>
          </table>
        </div>
        <p class="text-muted">There is no site 7. A site that is not on this list has to be added to the dashboard
           first, so please <a href="<?php echo esc_url(home_url('/about/')); ?>">contact the WELL team</a> before
           uploading data for a new site.</p>

        <h4 class="h5 mt-4">Parameters and units</h4>
        <p>Each value must be in the unit shown here. A different unit is an error (the value is not converted for
           you), so convert it yourself before uploading.</p>
        <div class="table-responsive">
          <table class="table table-sm sampling-ref" id="parameters-table">
            <thead><tr><th>Parameter</th><th>Unit</th><th>Also accepted as</th></tr></thead>
            <tbody>
              <tr><td>E. coli</td><td>CFU/100 mL</td><td>E.coli, E coli</td></tr>
              <tr><td>Total coliform</td><td>CFU/100 mL</td><td></td></tr>
              <tr><td>Turbidity</td><td>NTU</td><td></td></tr>
              <tr><td>pH</td><td>pH units (or pH)</td><td></td></tr>
              <tr><td>Conductivity</td><td>µS/cm</td><td>Specific conductance</td></tr>
              <tr><td>Chloride</td><td>mg/L</td><td></td></tr>
              <tr><td>Total phosphorus</td><td>µg/L</td><td>TP</td></tr>
              <tr><td>Soluble reactive phosphorus</td><td>µg/L</td><td>SRP</td></tr>
              <tr><td>Total nitrogen</td><td>mg/L</td><td>TN</td></tr>
              <tr><td>Nitrate nitrogen</td><td>mg/L</td><td>Nitrate-N</td></tr>
              <tr><td>Ammonia nitrogen</td><td>mg/L</td><td>Ammonia-N</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">3</span> Check your file (below)</h3>
        <p>Before you upload, drop your file into the <a href="#sampling-checker">Check my CSV format</a> tool at the
           bottom of this page. It tells you right away whether the file will import, and if not, exactly what to
           fix.</p>
      </div>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">4</span> Upload to Borealis</h3>
        <p>Sign in to Borealis and open the <strong>Ancaster Watershed Sampling Uploads</strong> dataset, then add
           your CSV as a new file.</p>
        <p>
          <a class="btn btn-primary" style="background-color:#fdbf57;color:#000;border-color:#fdbf57;"
             href="<?php echo esc_url($borealis_url); ?>" target="_blank" rel="noopener noreferrer">Open WELL on Borealis</a>
        </p>
        <p class="text-muted">If you do not yet have access to the dataset, ask the WELL team to add you.</p>
        <div class="sampling-shot" role="img" aria-label="Screenshot placeholder: adding a file on the Borealis dataset page">
          <span>Screenshot placeholder — the "Upload Files" step on the Borealis dataset. (Add your own image here.)</span>
        </div>
      </div>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">5</span> Publish, and confirm it worked</h3>
        <p>On Borealis, a newly added file is only picked up once the dataset version is <strong>published</strong>.
           Depending on your role, either you can publish it yourself or a dataset curator publishes it for you — if
           in doubt, let the WELL team know you have uploaded a file.</p>
        <p>After the next weekly import, your readings will show up on the dashboard's <strong>Ancaster
           Watershed</strong> tab. If something was wrong with the format, the file is set aside (nothing imported)
           and the WELL team is alerted with the specific problems, so your upload is never silently lost — you can
           fix it and upload a corrected file, which gets imported on the following run.</p>
      </div>

      <hr class="my-5">

      <!-- Common mistakes -->
      <h2>Common reasons a file is refused</h2>
      <p>The checker and the import both refuse a file for any of these. Each one tells you the exact row and
         column, so you can go straight to it.</p>
      <ul class="sampling-mistakes">
        <li>A required column (<code>date</code>, <code>site</code>, <code>parameter</code>, <code>value</code>, <code>unit</code>) is missing, duplicated, or a heading is mis-typed.</li>
        <li>A <code>date</code> that is not <code>YYYY-MM-DD</code>, or an impossible date like <code>2026-02-30</code>.</li>
        <li>A <code>time</code> that is not 24-hour <code>HH:MM</code>.</li>
        <li>A <code>site</code> that is not one of the known sites (a typo, or a site not yet added).</li>
        <li>A <code>parameter</code> that is not on the list, or a <code>unit</code> that does not match the parameter.</li>
        <li>A <code>value</code> that is not a plain number, or is impossible (a negative concentration, a pH above 14).</li>
        <li>The same reading twice (same site, parameter, date and time) — report one value per reading; average replicates and note it.</li>
        <li>The file saved as something other than CSV UTF-8, or with no readings in it at all.</li>
      </ul>

      <hr class="my-5">

      <!-- The checker tool -->
      <h2 id="sampling-checker">Check my CSV format</h2>
      <p>Paste the contents of your CSV, or choose the file, then press <strong>Check</strong>. Nothing is uploaded
         or stored — this only reads your file and tells you whether it would import. The dashboard runs the very
         same check the weekly import uses, so a pass here means a pass there.</p>

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
          file to Borealis — the weekly import will check it and the WELL team will tell you if anything needs
          fixing.</div>
      </noscript>

    </div>
  </section>
</main>

<?php
get_footer();
