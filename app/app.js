/*
================================================================================
 app/app.js  -  router + the three pages
================================================================================
 WHAT   : Hash routing, the drawer's close-on-navigate, a clock, and three small
          page renderers. No build step, no framework, no state library.
 WHY    : The shell stays under 100 lines of logic so the trading code (tape,
          footprint, signal, trade) can grow without dragging the UI with it.
 WHERE  : Futures/app.
 SCALE  : A page is a function returning HTML. Add one line to PAGES for a page.
================================================================================
*/

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ pages */
const PAGES = {
	signal: {
		title: 'Signal',
		render: () => `
			<div class="flex flex-col gap-4 page-enter">
				<section class="card">
					<div class="flex items-center justify-between">
						<span class="text-micro text-subtle">STATE</span>
						<span class="badge badge-neutral" id="state-badge">waiting</span>
					</div>
					<p class="text-hero mt-3" id="state-word">WAIT</p>
					<p class="text-meta text-dim mt-2" id="state-note">no signal yet</p>
				</section>

				<section class="card">
					<div class="flex items-center justify-between">
						<span class="text-micro text-subtle">LEVEL</span>
						<span class="text-micro text-subtle">PRICE</span>
					</div>
					<div class="flex items-baseline justify-between mt-2">
						<div>
							<p class="text-display" id="level">-</p>
							<p class="text-micro text-subtle mt-1" id="level-note">nearest level</p>
						</div>
						<div class="text-right">
							<p class="text-display" id="price">-</p>
							<p class="text-micro text-subtle mt-1" id="delta">delta -</p>
						</div>
					</div>
				</section>

				<section class="card">
					<p class="text-micro text-subtle">PLAN</p>
					<div class="mt-3 grid grid-cols-3 gap-3">
						<div><p class="text-micro text-subtle">stop</p><p class="text-title mt-1" id="stop">-</p></div>
						<div><p class="text-micro text-subtle">target</p><p class="text-title mt-1" id="target">-</p></div>
						<div><p class="text-micro text-subtle">risk</p><p class="text-title mt-1" id="risk">-</p></div>
					</div>
				</section>
			</div>`,
	},

	trades: {
		title: 'Trades',
		render: () => `
			<div class="card page-enter p-0">
				<table class="table">
					<thead>
						<tr>
							<th>TIME</th><th>SIDE</th><th class="num">PRICE</th>
							<th class="num">QTY</th><th class="num">NET</th>
						</tr>
					</thead>
					<tbody id="trades-body">
						<tr><td colspan="5" class="text-micro text-subtle">no trades yet</td></tr>
					</tbody>
				</table>
			</div>`,
	},

	log: {
		title: 'Log',
		render: () => `
			<div class="card page-enter">
				<p class="text-micro text-subtle">DECISIONS</p>
				<div id="log-body" class="mt-3 flex flex-col gap-2">
					<p class="text-meta text-dim">every gate, confirm and order appears here</p>
				</div>
			</div>`,
	},
};

/* ------------------------------------------------------------------ router */
function currentRoute() {
	const hash = location.hash.replace('#/', '');
	return PAGES[hash] ? hash : 'signal';
}

function render() {
	const route = currentRoute();
	const page = PAGES[route];

	$('title').textContent = page.title;
	$('page').innerHTML = page.render();

	for (const link of document.querySelectorAll('.nav-item')) {
		link.classList.toggle('active', link.dataset.route === route);
	}

	document.body.classList.remove('drawer-open');   // any navigation closes the drawer
}

/* ------------------------------------------------------------------ clock */
function tick() {
	$('clock').textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });
}

/* ------------------------------------------------------------------ boot */
window.addEventListener('hashchange', render);
addEventListener('DOMContentLoaded', () => {
	render();

	// the drawer: two buttons, one class, nothing else
	$('burger').addEventListener('click', () => document.body.classList.add('drawer-open'));
	$('scrim').addEventListener('click', () => document.body.classList.remove('drawer-open'));

	// dev hook: ?menu=open renders the drawer open, so the phone layout can be checked
	if (new URLSearchParams(location.search).get('menu') === 'open') {
		document.body.classList.add('drawer-open');
	}

	tick();
	setInterval(tick, 1000);
});
