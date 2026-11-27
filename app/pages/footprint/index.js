/*
================================================================================
 pages/footprint/index.js  -  the 5m footprint, last four bars
================================================================================
 WHAT   : Draws the last four 5-minute bars: three closed, one still forming.
          Each bar is a candle plus its bid x ask row per 0.1, with POC, BALLAST
          and (once the poller has seen it) IMBALANCE.

 WHY    : A footprint is read left to right as a story: the fight, the verdict,
          the follow-through, then the live bar. More than that is data to stare
          at, not information to act on.

 HOW TO SEE MORE BARS AGAIN
          One constant controls everything:

              const MAX_BARS = 4;
                            ^ set to 12, 20 or 30 and the chart shows that many.
                              The server already keeps 30 (KEEP in
                              engine/footprint/server.py).
                            ^ the styling is sized for four:
                              .fp-chart { width: fit-content; height: 420px; }
                              to go wide again use width: 100% and height: 560px.

 WHERE  : app/pages/footprint
 SCALE  : New visual piece -> components/. New data field -> server first.
================================================================================
*/

import axis from './components/axis.js';
import column from './components/column.js';

const STYLE = './pages/footprint/styles/footprint.css';
const POLL_MS = 2000;

/** how many bars the chart holds: 3 closed + the live one */
const MAX_BARS = 4;

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
						<p>last ${MAX_BARS} bars - bid x ask per 0.1 row - built from the live tape</p>
					</div>
					<span class="badge badge-neutral" id="fp-status">connecting</span>
				</header>
				<section class="fp-chart" id="fp-chart">
					<p class="fp-wait">waiting for the tape...</p>
				</section>
			</div>`;

		const tick = async () => {
			try {
				const response = await fetch(`/api/footprint?limit=${MAX_BARS}`, { cache: 'no-store' });
				const state = await response.json();
				if (element.isConnected) {
					draw(element, state);
				}
			} catch (error) {
				setStatus(element, 'offline', 'badge-danger');
			}
		};

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
			setTimeout(start, 300);
		}

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

	return all.slice(-MAX_BARS).map(bar => ({
		time: bar.time,
		current: Boolean(bar.current),
		poc: bar.poc === null || bar.poc === undefined ? null : Number(bar.poc).toFixed(1),
		pocSide: bar.pocSide,
		ballast: bar.ballast,
		imbalance: bar.imbalance,
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
		return;
	}

	const top = chart.scrollTop;
	const prices = priceGrid(bars);
	chart.innerHTML = bars.map(bar => column(bar, prices)).join('') + axis(prices);
	chart.scrollTop = top;

	// centre the live price when the set of bars changes
	const key = bars.map(bar => bar.time).join(',');
	if (key !== element.__key) {
		element.__key = key;
		centrePrice(chart, bars, prices);
	}
}

function centrePrice(chart, bars, prices) {
	const last = bars[bars.length - 1];
	const row = prices.findIndex(price => Math.abs(price - last.close) < 0.1001);
	if (row < 0) {
		return;
	}

	const rowHeight = chart.querySelector('.fp-price')?.getBoundingClientRect().height || 18;
	chart.scrollTop = Math.max(0, row * rowHeight - chart.clientHeight / 2);
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
