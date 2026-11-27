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
// one rate, from your own deposit: 23.70 USDT came to KSh 3,100
const KES_PER_USDT = 130.80;
// the real futures wallet, read by the server with the live keys
async function paintBalance() {
	const node = $('balance');
	if (!node) {
		return;
	}

	try {
		const response = await fetch('/api/balance', { cache: 'no-store' });
		const value = await response.json();

		if (typeof value.available !== 'number') {
			node.innerHTML = '<span class="text-micro text-subtle">KSh --</span>';
			return;
		}

		const money = (amount) => amount.toLocaleString('en-US', {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2,
		});

		const pnl = Number(value.pnl || 0);
		const colour = pnl > 0 ? '#34d399' : pnl < 0 ? '#fb7185' : '#8b94a7';
		const sign = pnl > 0 ? '+' : '';

		const kes = (amount) => (amount * KES_PER_USDT).toLocaleString('en-US', {
			minimumFractionDigits: 0,
			maximumFractionDigits: 0,
		});

		node.innerHTML = `<span class="text-micro text-subtle">KSh</span> ${kes(value.available)}`
			+ `<span style="margin-left:10px;font-size:12px;font-variant-numeric:tabular-nums;color:${colour}">`
			+ `${sign}KSh ${kes(Math.abs(pnl))}</span>`;
	} catch (error) {
		node.innerHTML = '<span class="text-micro text-subtle">KSh --</span>';
	}
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
	setInterval(paintBalance, 2000);
	setInterval(tick, 1000);

	// the drawer: two buttons, one class, nothing else
	$('burger').addEventListener('click', () => document.body.classList.add('drawer-open'));
	$('scrim').addEventListener('click', () => document.body.classList.remove('drawer-open'));

	// dev hook: ?menu=open renders the drawer open, so the phone layout can be checked
	if (new URLSearchParams(location.search).get('menu') === 'open') {
		document.body.classList.add('drawer-open');
	}
});
