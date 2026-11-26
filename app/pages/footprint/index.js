/*
================================================================================
 pages/footprint/index.js  -  the 5m footprint page
================================================================================
 WHAT   : Fetches /api/footprint every 2 s and draws the finished bars plus the
          one still forming. Candle and bid x ask rows, nothing else.
 WHY    : The page is a viewer. The server owns the tape and the 5-minute clock;
          the page owns pixels.
 WHERE  : app/pages/footprint
 SCALE  : New visual piece -> components/. New data field -> server first.
================================================================================
*/

import axis from './components/axis.js';
import column from './components/column.js';

const STYLE = './pages/footprint/styles/footprint.css';
const POLL_MS = 2000;

export default {
	title: 'Footprint',

	mount(element) {
		if (!document.querySelector(`link[href="${STYLE}"]`)) {
			const link = document.createElement('link');
			link.rel = 'stylesheet';
			link.href = STYLE;
			document.head.appendChild(link);
		}

		element.innerHTML = `
			<div class="page-enter fp-page">
				<header class="fp-head">
					<div>
						<h2>BNB PERP - 5m footprint</h2>
						<p>5 minutes per bar - bid x ask per 0.1 row - built from the live tape</p>
					</div>
					<span class="badge badge-neutral" id="fp-status">connecting</span>
				</header>
				<section class="fp-chart" id="fp-chart">
					<p class="fp-wait">waiting for the tape...</p>
				</section>
			</div>`;

		const tick = async () => {
			try {
				const response = await fetch('/api/footprint', { cache: 'no-store' });
				const state = await response.json();
				if (element.isConnected) {
					draw(element, state);
				}
			} catch (error) {
				setStatus(element, 'offline', 'badge-danger');
			}
		};

		tick();
		this.timer = setInterval(tick, POLL_MS);
	},

	unmount() {
		clearInterval(this.timer);
	},
};

/* server shape -> what a column needs. bid = taker sells, ask = taker buys */
function toView(state) {
	const all = [...(state.bars || [])];
	if (state.current) {
		all.push(state.current);
	}

	return all.map(bar => ({
		time: bar.time,
		current: Boolean(bar.current),
		poc: bar.poc === null || bar.poc === undefined ? null : Number(bar.poc).toFixed(1),
		pocSide: bar.pocSide,
		open: bar.open, close: bar.close, high: bar.high, low: bar.low,
		rows: Object.fromEntries(
			Object.entries(bar.rows || {}).map(([price, volume]) => [
				price,
				[Number(volume.sell.toFixed(2)), Number(volume.buy.toFixed(2))],
			]),
		),
	}));
}

function draw(element, state) {
	const chart = element.querySelector('#fp-chart');
	if (!chart) {
		return;
	}

	setStatus(element, state.live ? 'live' : 'silent', state.live ? 'badge-success' : 'badge-warning');

	const bars = toView(state);
	if (!bars.length) {
		chart.innerHTML = '<p class="fp-wait">no fills in this window yet...</p>';
		chart.dataset.scrolled = '';
		return;
	}

	const prices = priceGrid(bars);
	chart.innerHTML = bars.map(bar => column(bar, prices)).join('') + axis(prices);

	// always look at the newest bar, unless the reader has scrolled back
	if (!chart.dataset.scrolled || chart.scrollLeft + chart.clientWidth >= chart.scrollWidth - 40) {
		chart.scrollLeft = chart.scrollWidth;
	}
}

function setStatus(element, text, tone) {
	const status = element.querySelector('#fp-status');
	if (status) {
		status.className = `badge ${tone}`;
		status.textContent = text;
	}
}

/* every price the shown bars touched, high to low, at 0.1 steps */
function priceGrid(bars) {
	const high = Math.max(...bars.map(bar => bar.high));
	const low = Math.min(...bars.map(bar => bar.low));
	const prices = [];

	for (let price = Math.ceil(high * 10) / 10; price >= Math.floor(low * 10) / 10 - 1e-9; price -= 0.1) {
		prices.push(Number(price.toFixed(1)));
	}
	return prices;
}
