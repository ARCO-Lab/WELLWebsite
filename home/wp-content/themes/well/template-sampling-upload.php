<?php
/**
 * Template Name: Sampling Data Upload Guide
 *
 * A link-only help page for researchers who have creek sampling data to contribute. It explains, in plain language,
 * how the data pipeline works and how to format and upload a CSV so it imports without errors, and it embeds a
 * "Check my CSV format" tool.
 *
 * The guide PROSE (headings and paragraphs) is now editable in wp-admin: it lives in the page's block content and is
 * rendered by the_content() below, inside the .sampling-guide container the guide's CSS is scoped to. The pieces that
 * must stay exact or functional are kept in code and placed in that content: the reference lists/tables that
 * js/sampling-check.js refreshes by id, the SVG diagrams, the screenshot figures and the styled buttons are preserved
 * as HTML blocks, and the live checker is the [well_sampling_checker] shortcode.
 *
 * The checker does NOT keep a second copy of the format rules: it posts the file to the dashboard's
 * /api/samples/validate, which runs the real import validator (dashboard/backend/app/utils/sampling_csv.py), so its
 * verdict is exactly what the weekly Borealis import would say. The reference tables are a static fallback that
 * js/sampling-check.js refreshes from /api/samples/format (the same lists), so they can't drift either.
 *
 * This template is assigned to a Page with an unlisted slug, kept out of the nav menus, and marked noindex by
 * well_sampling_upload_noindex() in functions.php, so the page is reachable only by its link.
 *
 * Images: the checker screenshots (img/sampling/sampling-checker-*.webp) are real captures of this page's own tool,
 * and the spreadsheet and "#####" pictures are our own illustrations. The Borealis step keeps an original diagram,
 * not a screenshot: do not paste branded Borealis/McMaster screenshots you do not have the right to publish. A WELL
 * team member with Borealis access can drop a real screenshot into img/sampling/ and swap it in later.
 */
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

// The guide's styling (css/sampling-check.css) is needed for the whole page, not just the checker, so load it here.
// The [well_sampling_checker] shortcode loads the checker's JavaScript when it is present in the content.
wp_enqueue_style(
  'well-sampling-check',
  get_template_directory_uri() . '/css/sampling-check.css',
  array(),
  well_asset_version('/css/sampling-check.css')
);

// Used only by the legacy fallback body below. Same resolution as page-dashboard.php.
$dashboard_url   = rtrim(getenv('DASHBOARD_URL') ?: 'https://welldash.mcmaster.ca', '/');
$template_url    = $dashboard_url . '/api/sampling-template';
$borealis_url    = 'https://borealisdata.ca/dataverse/WELL';
$img_base        = get_template_directory_uri() . '/img/sampling';

get_header();
?>

<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-2">Uploading your creek sampling data</h1>
        <p class="lead mb-0">Thanks for collecting data for WELL. This page shows you how to put your sampling results into a file the dashboard can read, and it has a little tool at the bottom that checks the file before you send it.</p>
      </div>
    </div>
  </div>
</header>

<main id="site-content">
  <section class="section-padding">
    <div class="container sampling-guide">
<?php
while (have_posts()) :
  the_post();

  if ('' !== trim(wp_strip_all_tags(get_the_content()))) {
    the_content();
  } else {
    // Not migrated yet: render the original guide body so the page is never blank.
?>

      <!-- Intro / how the pipeline works -->
      <div class="row">
        <div class="col-lg-8">
          <h2>How your data reaches the dashboard</h2>
          <p>When you have sampling results from the Ancaster Creek watershed, you share them as a spreadsheet saved
             as a <strong>CSV file</strong> and upload it to our <strong>Borealis</strong> data repository. From
             there, nobody has to copy anything by hand:</p>
          <ol>
            <li>You upload your CSV to the <em>Ancaster Watershed Sampling Uploads</em> dataset on Borealis.</li>
            <li>Once a week, WELL picks up any new files from that dataset.</li>
            <li>Each file is <strong>checked against the standard format</strong>, and if it passes, every reading in
                it is imported for you.</li>
            <li>Your readings show up on the dashboard's <strong>Ancaster Watershed</strong> tab, where anyone can
                view and download them.</li>
          </ol>
          <p>If a file doesn't match the format, <strong>none of it is imported</strong> and the WELL team gets a
             heads-up to look into it. Your data is never half-imported, so it really is worth getting the format
             right the first time. That is what the rest of this page is for.</p>
        </div>
        <div class="col-lg-4">
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
        <p>The easiest way to start is from the blank template. It already has the column headings in the right
           order, plus a few example rows to show you the idea:</p>
        <p>
          <a class="btn btn-primary" style="background-color:#fdbf57;color:#000;border-color:#fdbf57;"
             href="<?php echo esc_url($template_url); ?>">Download the CSV template</a>
        </p>
        <p class="text-muted">Open it in Excel, Google Sheets or Numbers, whatever you normally use. Leave the
           heading row exactly as it is.</p>

        <div class="alert-box alert-box--info">
          <strong>Seeing <code>#####</code> where a date should be?</strong> That is just Excel saying the column is
          too narrow to show the whole date, not a sign that anything is wrong. Double-click the line between the
          column letters (or drag it wider) and the date comes right back. The one thing to check is that your dates
          read as <code>YYYY-MM-DD</code>, for example <code>2026-05-06</code>, when the column is wide enough to see
          them.
        </div>
        <figure class="sampling-figure">
          <img src="<?php echo esc_url($img_base . '/sampling-excel-hash.webp'); ?>" width="1200" height="207"
               loading="lazy" decoding="async"
               alt="A spreadsheet with a date column too narrow to read, showing #####, next to the same column widened to show 2026-05-06.">
          <figcaption>Left: a narrow column hides the date behind <code>#####</code>. Right: widen the column and the
             date is there, in <code>YYYY-MM-DD</code> form.</figcaption>
        </figure>
      </div>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">2</span> Fill in your readings</h3>
        <p>The one rule to remember: <strong>one reading per row</strong>. If you measured nine things at a site on a
           single visit, that is nine rows, one for each parameter. Here is what goes in each column:</p>

        <h4 class="h5 mt-4">Required in every row</h4>
        <ul class="sampling-cols" id="required-columns">
          <li><code>date</code>: the sampling date as <code>YYYY-MM-DD</code>, for example <code>2026-05-06</code>.</li>
          <li><code>site</code>: one of the sites in the table below.</li>
          <li><code>parameter</code>: one of the parameters in the table below.</li>
          <li><code>value</code>: a plain number, for example <code>1295</code> or <code>0.015</code>.</li>
          <li><code>unit</code>: the parameter's unit, exactly as listed below.</li>
        </ul>

        <h4 class="h5 mt-4">Optional (fill in if you have them)</h4>
        <ul class="sampling-cols" id="optional-columns">
          <li><code>time</code>: the time of sampling in 24-hour <code>HH:MM</code>, for example <code>14:05</code>, in local Hamilton time.</li>
          <li><code>creek</code>: the creek's name. We use it to double-check you picked the right site.</li>
          <li><code>below_detection</code>: <code>true</code> if the value was below the detection limit.</li>
          <li><code>qc_flag</code>: <code>ok</code>, <code>suspect</code> or <code>rejected</code>.</li>
          <li><code>sampler</code>, <code>method</code>, <code>notes</code>: anything else worth keeping with the reading.</li>
        </ul>

        <figure class="sampling-figure">
          <img src="<?php echo esc_url($img_base . '/sampling-template-spreadsheet.webp'); ?>" width="1200" height="259"
               loading="lazy" decoding="async"
               alt="The template open in a spreadsheet: a header row of column names and example rows, one reading per row, with dates in YYYY-MM-DD form.">
          <figcaption>A filled-in template, one reading per row. (This is an example; your sites and parameters will
             differ.)</figcaption>
        </figure>

        <div class="alert-box alert-box--info">
          <strong>A few things that trip people up:</strong>
          <ul class="mb-0">
            <li><strong>Dates must be <code>YYYY-MM-DD</code>.</strong> Something like <code>05/06/2026</code> is turned away, because it could mean 5 June or 6 May and the system won't guess.</li>
            <li><strong>Values are plain numbers.</strong> No commas for thousands, and no units in the cell. The unit goes in the <code>unit</code> column.</li>
            <li><strong>Below the detection limit?</strong> Write the limit with a <code>&lt;</code> in front, like <code>&lt;0.01</code>.</li>
            <li><strong>Didn't measure something?</strong> Just leave that row out, or leave <code>value</code> empty. Please don't write <code>0</code> to mean "not measured".</li>
            <li><strong>Save as CSV UTF-8.</strong> In Excel that is <em>File &gt; Save As &gt; CSV UTF-8 (Comma delimited)</em>.</li>
          </ul>
        </div>

        <h4 class="h5 mt-4">Sites</h4>
        <p>You can use the site's name, its number, or both (for example <code>Falkirk Forest</code>, <code>1</code>,
           or <code>#1 Falkirk Forest</code>). Spelling matters; capitals and extra spaces don't.</p>
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
        <p class="text-muted">There is no site 7. A site that isn't on this list has to be added to the dashboard
           first, so please <a href="<?php echo esc_url(home_url('/about/')); ?>">get in touch with the WELL team</a>
           before uploading data for a new site.</p>

        <h4 class="h5 mt-4">Parameters and units</h4>
        <p>Each value needs to be in the unit shown here. A different unit is treated as an error (we don't convert it
           for you), so do the conversion yourself before you upload.</p>
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
        <h3><span class="sampling-step__num">3</span> Check your file (right here)</h3>
        <p>Before you upload anything, drop your file into the <a href="#sampling-checker">Check my CSV format</a>
           tool at the bottom of this page. It tells you straight away whether the file will import, and if it won't,
           it points you to exactly what to fix.</p>
        <figure class="sampling-figure">
          <img src="<?php echo esc_url($img_base . '/sampling-checker-pass.webp'); ?>" width="1100" height="716"
               loading="lazy" decoding="async"
               alt="The Check my CSV format tool showing a green 'Looks good' banner after checking a valid file.">
          <figcaption>When a file is good to go, you get a green "Looks good" and a quick count of what it holds.</figcaption>
        </figure>
        <figure class="sampling-figure">
          <img src="<?php echo esc_url($img_base . '/sampling-checker-fix.webp'); ?>" width="1100" height="946"
               loading="lazy" decoding="async"
               alt="The Check my CSV format tool showing a red 'Not ready yet' banner and a table listing each problem with its row, column and what to fix.">
          <figcaption>When something is off, it lists each problem with its row, column and a plain-English note on
             what to change.</figcaption>
        </figure>
      </div>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">4</span> Upload to Borealis</h3>
        <p>Sign in to Borealis and open the <strong>Ancaster Watershed Sampling Uploads</strong> dataset, then add
           your CSV as a new file.</p>
        <p>
          <a class="btn btn-primary" style="background-color:#fdbf57;color:#000;border-color:#fdbf57;"
             href="<?php echo esc_url($borealis_url); ?>" target="_blank" rel="noopener noreferrer">Open WELL on Borealis</a>
        </p>
        <p class="text-muted">If you don't have access to the dataset yet, just ask the WELL team to add you.</p>

        <figure class="sampling-figure" aria-hidden="false">
          <svg viewBox="0 0 640 150" width="100%" height="auto" role="img" aria-labelledby="bor-title bor-desc">
            <title id="bor-title">Uploading a file on Borealis, in three steps</title>
            <desc id="bor-desc">Open the Sampling Uploads dataset, use Edit then Upload Files to add your CSV, then save the changes.</desc>
            <g font-family="Poppins, sans-serif" font-size="13" text-anchor="middle">
              <rect x="10" y="30" width="180" height="70" rx="10" fill="#fff" stroke="#7a003c" stroke-width="2"></rect>
              <text x="100" y="60" fill="#7a003c" font-weight="600">1. Open the dataset</text>
              <text x="100" y="80" fill="#495965" font-size="11">Sampling Uploads</text>
              <line x1="190" y1="65" x2="228" y2="65" stroke="#495965" stroke-width="2" marker-end="url(#bor-arrow)"></line>
              <rect x="230" y="30" width="180" height="70" rx="10" fill="#fff" stroke="#7a003c" stroke-width="2"></rect>
              <text x="320" y="60" fill="#7a003c" font-weight="600">2. Add your CSV</text>
              <text x="320" y="80" fill="#495965" font-size="11">Edit &gt; Upload Files</text>
              <line x1="410" y1="65" x2="448" y2="65" stroke="#495965" stroke-width="2" marker-end="url(#bor-arrow)"></line>
              <rect x="450" y="30" width="180" height="70" rx="10" fill="#7a003c"></rect>
              <text x="540" y="60" fill="#fff" font-weight="600">3. Save</text>
              <text x="540" y="80" fill="#fdbf57" font-size="11">then publish (step 5)</text>
            </g>
            <defs>
              <marker id="bor-arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 Z" fill="#495965"></path>
              </marker>
            </defs>
          </svg>
          <figcaption>The three steps on Borealis. This is an illustration, not a Borealis screenshot; the buttons may
             be labelled slightly differently depending on your role.</figcaption>
        </figure>
      </div>

      <div class="sampling-step">
        <h3><span class="sampling-step__num">5</span> Publish, and confirm it worked</h3>
        <p>On Borealis, a file you've just added is only picked up once the dataset version is
           <strong>published</strong>. Depending on your role, you can either publish it yourself or a dataset curator
           publishes it for you. If you aren't sure which, just let the WELL team know you've uploaded a file.</p>
        <p>After the next weekly import, your readings will appear on the dashboard's <strong>Ancaster
           Watershed</strong> tab. If something was off with the format, the file is set aside (nothing from it is
           imported) and the WELL team is told exactly what the problems were, so your upload is never quietly lost.
           You fix it, upload a corrected file, and it goes in on the following run.</p>
      </div>

      <hr class="my-5">

      <!-- Common mistakes -->
      <h2>Common reasons a file is turned away</h2>
      <p>The checker and the weekly import both refuse a file for any of these, and each one tells you the exact row
         and column so you can go straight to it:</p>
      <ul class="sampling-mistakes">
        <li>A required column (<code>date</code>, <code>site</code>, <code>parameter</code>, <code>value</code>, <code>unit</code>) is missing or duplicated, or a heading is mis-typed.</li>
        <li>A <code>date</code> that isn't <code>YYYY-MM-DD</code>, or an impossible one like <code>2026-02-30</code>.</li>
        <li>A <code>time</code> that isn't a 24-hour <code>HH:MM</code>.</li>
        <li>A <code>site</code> that isn't one of the known sites (a typo, or a site not added yet).</li>
        <li>A <code>parameter</code> that isn't on the list, or a <code>unit</code> that doesn't match the parameter.</li>
        <li>A <code>value</code> that isn't a plain number, or is impossible (a negative concentration, or a pH above 14).</li>
        <li>The same reading twice (same site, parameter, date and time). Report one value per reading; if you have replicates, average them and say so in <code>notes</code>.</li>
        <li>The file saved as something other than CSV UTF-8, or a file with no readings in it at all.</li>
      </ul>

      <hr class="my-5">

      <!-- The checker tool -->
      <?php get_template_part('sections/sampling-checker'); ?>
<?php
  }
endwhile;
?>
    </div>
  </section>
</main>

<?php
get_footer();
