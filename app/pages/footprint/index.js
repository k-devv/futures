/*
================================================================================
 pages/footprint/index.js  -  the 5m footprint page
================================================================================
 WHAT   : Fetches /api/footprint every 2 s and draws the closed bars plus the one
          still forming. Candle, bid x ask rows, POC, BALLAST. Nothing else.
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
const FETCH_BARS = 30;     // ask for the maximum; the page trims to what fits

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
				const response = await fetch(`/api/footprint?limit=${FETCH_BARS}`, { cache: 'no-store' });
				const state = await response.json();
				if (element.isConnected) {
					await draw(element, state);
				}
			} catch (error) {
				setStatus(element, 'offline', 'badge-danger');
			}
		};

		this.onResize = () => tick();
		window.addEventListener('resize', this.onResize);

		const start = () => setTimeout(tick, 60);
		if (document.querySelector(`link[href="${STYLE}"]`)) {
			start();
		} else {
			const observer = new MutationObserver(() => {
				if (document.querySelector(`link[href="${STYLE}"]`)) {
					observer.disconnect();
					start();
				}
			});
			observer.observe(document.head, { childList: true });
			setTimeout(start, 300);        // never wait forever for a stylesheet
		}

		this.timer = setInterval(tick, POLL_MS);
	},

	unmount() {
		clearInterval(this.timer);
		window.removeEventListener('resize', this.onResize);
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
		ballast: bar.ballast,
		open: bar.open, close: bar.close, high: bar.high, low: bar.low,
		rows: Object.fromEntries(
			Object.entries(bar.rows || {}).map(([price, volume]) => [
				price,
				[Number(volume.sell.toFixed(2)), Number(volume.buy.toFixed(2))],
			]),
		),
	}));
}

async function draw(element, state) {
	const chart = element.querySelector('#fp-chart');
	if (!chart) {
		return;
	}

	setStatus(element, state.live ? 'live' : 'silent', state.live ? 'badge-success' : 'badge-warning');

	const bars = toView(state);
	if (!bars.length) {
		chart.innerHTML = '<p class="fp-wait">no fills in this window yet...</p>';
		return;
	}

	// draw, let the browser lay it out, and drop the oldest bar while it overflows.
	// only the newest bars survive, which is exactly what we want to look at.
	let shown = bars;
	for (let guard = 0; guard < 60; guard += 1) {
		renderInto(chart, shown);
		await new Promise(resolve => requestAnimationFrame(resolve));

		if (chart.scrollWidth <= chart.clientWidth + 1 || shown.length <= 2) {
			break;
		}
		shown = shown.slice(1);
	}

	// keep the live price in the middle of the visible prices
	const last = shown[shown.length - 1];
	const prices = priceGrid(shown);
	const row = prices.findIndex(price => Math.abs(price - last.close) < 0.1001);
	if (row >= 0) {
		const rowHeight = chart.querySelector('.fp-price')?.getBoundingClientRect().height || 18;
		chart.scrollTop = Math.max(0, row * rowHeight - chart.clientHeight / 2);
	}
}

function renderInto(chart, bars) {
	const prices = priceGrid(bars);
	chart.innerHTML = bars.map(bar => column(bar, prices)).join('') + axis(prices);
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
