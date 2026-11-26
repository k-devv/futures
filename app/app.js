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

import signal from './pages/signal/index.js';
import trades from './pages/trades/index.js';
import log from './pages/log/index.js';

const $ = (id) => document.getElementById(id);

const PAGES = { signal, trades, log };

/* ------------------------------------------------------------------ routing */
function currentRoute() {
	const hash = location.hash.replace('#/', '');
	return PAGES[hash] ? hash : 'signal';
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

/* ------------------------------------------------------------------ clock */
function tick() {
	$('clock').textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });
}

/* ------------------------------------------------------------------ boot */
window.addEventListener('hashchange', render);

addEventListener('DOMContentLoaded', () => {
	render();
	tick();
	setInterval(tick, 1000);

	// the drawer: two buttons, one class, nothing else
	$('burger').addEventListener('click', () => document.body.classList.add('drawer-open'));
	$('scrim').addEventListener('click', () => document.body.classList.remove('drawer-open'));

	// dev hook: ?menu=open renders the drawer open, so the phone layout can be checked
	if (new URLSearchParams(location.search).get('menu') === 'open') {
		document.body.classList.add('drawer-open');
	}
});
