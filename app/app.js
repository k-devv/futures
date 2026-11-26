/*
================================================================================
 app/app.js  -  the shell's logic: routing, the drawer, the clock
================================================================================
 WHAT   : Imports the three pages, routes the hash to one of them, and mounts it
          into #page. Closes the drawer, ticks the clock.
 WHY    : The shell knows nothing about trading. Every page is a folder that
          exports { title, mount }, so this file never grows with features.
 WHERE  : app/
 SCALE  : A new page is one import and one PAGES entry.
================================================================================
*/

import footprint from './pages/footprint/index.js';


const $ = (id) => document.getElementById(id);

const PAGES = { footprint };

/* ------------------------------------------------------------------ routing */
function currentRoute() {
	const hash = location.hash.replace('#/', '');
	return PAGES[hash] ? hash : 'footprint';
}

function render() {
	const route = currentRoute();
	const page = PAGES[route];

	$('title').textContent = page.title;

	// a fresh container every time, so a page never inherits the last one's DOM
	$('page').innerHTML = '';
	page.mount($('page'));

	for (const link of document.querySelectorAll('.nav-item')) {
		link.classList.toggle('active', link.dataset.route === route);
	}

	document.body.classList.remove('drawer-open');   // navigation closes the drawer
}

/* ------------------------------------------------------------------ balance */
// dummy until the account feed exists: one constant, one formatter, one element
const DUMMY_BALANCE = 5000;

function paintBalance(usdt = DUMMY_BALANCE) {
	$('balance').innerHTML = `${usdt.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	})} <span class="text-micro text-subtle">USDT</span>`;
}

/* ------------------------------------------------------------------ clock */
function tick() {
	$('clock').textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });
}

/* ------------------------------------------------------------------ boot */
window.addEventListener('hashchange', render);

addEventListener('DOMContentLoaded', () => {
	render();
	tick();
	paintBalance();
	setInterval(tick, 1000);

	// the drawer: two buttons, one class, nothing else
	$('burger').addEventListener('click', () => document.body.classList.add('drawer-open'));
	$('scrim').addEventListener('click', () => document.body.classList.remove('drawer-open'));

	// dev hook: ?menu=open renders the drawer open, so the phone layout can be checked
	if (new URLSearchParams(location.search).get('menu') === 'open') {
		document.body.classList.add('drawer-open');
	}
});
