/*
================================================================================
 pages/footprint/index.js  -  the 5m footprint, last four bars, OI only
================================================================================
 WHAT   : Draws the last four 5-minute bars - three closed, one live - as a
          candle panel above and a bid x ask grid below, then one checklist line:
          the newest open-interest number Binance has published, in BNB.

 WHY    : Open interest is the one number that shows whether money stayed in the
          market or left it. Everything else on this page exists to show where
          that money fought.

 HOW TO SEE MORE BARS AGAIN
              const MAX_BARS = 4;      <- set 12, 20 or 30
          the styling is sized for four:
              .fp-chart { --colw: 136px }  and the candle panel at 50% height.
          to go wide again use width: 100% on .fp-wrap.

 WHERE  : app/pages/footprint
 SCALE  : New visual piece -> components/. New data field -> server first.
================================================================================
*/

import axis from './components/axis.js';
import candles from './components/candles.js';
import column from './components/column.js';

const STYLE = './pages/footprint/styles/footprint.css';
const POLL_MS = 2000;
const MAX_BARS = 4;
const PANEL_HEIGHT = 420;

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

				<section class="fp-wrap">
					<div class="fp-candles" id="fp-candles"></div>
					<section class="fp-chart" id="fp-chart">
						<p class="fp-wait">waiting for the tape...</p>
					</section>
				</section>

				<section class="fp-check" id="fp-check">
					<h3 class="fp-check-title">Checklist</h3>
					<div class="fp-check-line" id="fp-ballast">
						<span class="k">1 OPEN INTEREST</span>
						<span class="v">waiting for open interest...</span>
					</div>
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

	// rows never shrink below readable size: in a fast move the grid scrolls
	const rowHeight = 18;
	const panelHeight = Math.min(prices.length * rowHeight + 28, PANEL_HEIGHT);
	chart.style.setProperty('--row', `${rowHeight}px`);
	chart.style.height = `${panelHeight}px`;

	const candlePanel = element.querySelector('#fp-candles');
	if (candlePanel) {
		candlePanel.style.height = `${Math.round(panelHeight * 0.5)}px`;
	}

	chart.innerHTML = bars.map(bar => column(bar, prices)).join('') + axis(prices);
	chart.scrollTop = top;

	paintCandles(element, bars);
	paintCheck(element, bars);

	// centre the live price when the set of bars changes
	const key = bars.map(bar => bar.time).join(',');
	if (key !== element.__key) {
		element.__key = key;
		centrePrice(chart, bars, prices);
	}
}

/* the candle panel: same columns, its own vertical scale */
function paintCandles(element, bars) {
	const panel = element.querySelector('#fp-candles');
	if (!panel) {
		return;
	}

	const low = Math.min(...bars.map(bar => bar.low));
	const high = Math.max(...bars.map(bar => bar.high));

	panel.innerHTML = bars.map(bar => candles(bar, low, high)).join('') + '<div class="fp-candle-axis"></div>';
}

/* the one line under the grid: the newest open-interest number Binance gave us */
function paintCheck(element, bars) {
	const node = element.querySelector('#fp-ballast .v');
	if (!node) {
		return;
	}

	const withOi = [...bars].reverse().find(bar => bar.ballast);
	if (!withOi) {
		node.innerHTML = '<span class="na">no open interest yet</span>';
		node.className = 'v';
		return;
	}

	const change = Math.round(withOi.ballast.change);
	const tone = change > 0 ? 'ok' : change < 0 ? 'no' : 'near';
	const sign = change > 0 ? '+' : '';
	const word = change > 0 ? 'BNB added' : change < 0 ? 'BNB left' : 'BNB flat';
	const received = withOi.ballast.received
		? new Date(withOi.ballast.received).toTimeString().slice(0, 8)
		: '--:--:--';

	node.innerHTML = `<span class="t">arrived ${received}</span> `
		+ `<span class="${tone}">${sign}${change}</span> <span class="say">${word}</span>`;
	node.className = 'v';
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
