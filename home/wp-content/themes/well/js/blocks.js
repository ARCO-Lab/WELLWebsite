/*
 * Editor definitions for the WELL developer-owned dynamic blocks (registered server-side in
 * inc/blocks.php). Each block previews its REAL server-rendered HTML in the editor with a
 * <ServerSideRender>, so an editor SEES the team cards, the dashboard embed and the CSV checker
 * while editing, instead of a bare "Shortcode" placeholder.
 *
 * No build step: this is plain ES5 using the wp.* globals that WordPress ships (wp-blocks,
 * wp-element, wp-block-editor, wp-components, wp-server-side-render, wp-i18n). The blocks have no
 * attributes and save null (they are dynamic — the front end is rendered by the PHP render_callback,
 * which outputs the same sections/*.php partial the old shortcode did).
 *
 * The preview is static HTML: JavaScript-driven bits (the Flickity carousels, the checker's file
 * handling, the team modals) only come alive on the published page, not in the editor canvas. That
 * is expected and noted for editors in EDITOR-HANDBOOK.md.
 */
( function ( blocks, element, blockEditor, components, serverSideRenderModule, i18n ) {
	'use strict';

	var el = element.createElement;
	var __ = i18n.__;
	var useBlockProps = blockEditor.useBlockProps;
	var Placeholder = components.Placeholder;
	var Spinner = components.Spinner;
	// @wordpress/server-side-render exposes its component as the default export.
	var ServerSideRender = serverSideRenderModule && ( serverSideRenderModule.default || serverSideRenderModule );

	// name: the block name (matches inc/blocks.php). title/description/icon: how it reads in the inserter.
	var WELL_BLOCKS = [
		{
			name: 'well/hero-carousel',
			title: __( 'WELL: Home Hero Carousel', 'well' ),
			description: __( 'The homepage rotating hero banner. Maintained in code; place or move it, but its slides are edited by a developer.', 'well' ),
			icon: 'images-alt2'
		},
		{
			name: 'well/latest-news',
			title: __( 'WELL: Latest News Strip', 'well' ),
			description: __( 'A carousel of the most recent posts. Updates itself as news is published.', 'well' ),
			icon: 'megaphone'
		},
		{
			name: 'well/dashboard-embed',
			title: __( 'WELL: Dashboard Embed', 'well' ),
			description: __( 'The live WELL data dashboard, embedded from the dashboard app.', 'well' ),
			icon: 'chart-area'
		},
		{
			name: 'well/dashboard-card',
			title: __( 'WELL: Dashboard Card', 'well' ),
			description: __( 'The homepage "The WELL Dashboard" card describing and linking to the dashboard.', 'well' ),
			icon: 'id'
		},
		{
			name: 'well/team',
			title: __( 'WELL: Team Grid', 'well' ),
			description: __( 'The About page "Our Team" cards. Each card is wired to its own contact pop-up in code.', 'well' ),
			icon: 'groups'
		},
		{
			name: 'well/sampling-checker',
			title: __( 'WELL: Sampling CSV Checker', 'well' ),
			description: __( 'The interactive "Check my CSV format" tool. Talks to the dashboard\'s real validator.', 'well' ),
			icon: 'yes-alt'
		}
	];

	WELL_BLOCKS.forEach( function ( block ) {
		blocks.registerBlockType( block.name, {
			apiVersion: 3,
			title: block.title,
			description: block.description,
			icon: block.icon,
			category: 'well',
			// Developer-owned: no settings to edit, so lock it against duplication/removal mishaps as little
			// as possible while keeping it a single whole piece.
			supports: {
				html: false,
				reusable: false,
				customClassName: false
			},
			edit: function () {
				var blockProps = useBlockProps( { className: 'well-ssr-block' } );
				var preview;
				if ( ServerSideRender ) {
					preview = el( ServerSideRender, {
						block: block.name,
						// Show a spinner instead of a flash of "empty" while the preview loads.
						EmptyResponsePlaceholder: function () {
							return el( Placeholder, { label: block.title }, el( Spinner, null ) );
						},
						LoadingResponsePlaceholder: function () {
							return el( Placeholder, { label: block.title }, el( Spinner, null ) );
						}
					} );
				} else {
					// Older WordPress without the server-side-render package: keep a clear labelled box.
					preview = el( Placeholder, {
						icon: block.icon,
						label: block.title,
						instructions: block.description
					} );
				}
				return el( 'div', blockProps, preview );
			},
			// Dynamic block: the server render_callback produces the front-end HTML.
			save: function () {
				return null;
			}
		} );
	} );
} )(
	window.wp.blocks,
	window.wp.element,
	window.wp.blockEditor,
	window.wp.components,
	window.wp.serverSideRender,
	window.wp.i18n
);
