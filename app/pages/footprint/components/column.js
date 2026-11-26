/*
================================================================================
 pages/footprint/components/column.js
================================================================================
 WHAT   : One 5m bar: the time, the candle, one bid×ask cell per price row, and
          delta/volume underneath.
 WHY    : A column is the unit a trader actually reads. Everything else on the
          page is this, repeated.
 WHERE  : app/pages/footprint/components
 SCALE  : Pure function: bar in, HTML out. No DOM lookups, no state.
================================================================================
*/

export default function column(bar, prices) {
	const rowOf = (price) => {
		let best = 0;
		let distance = Infinity;
		prices.forEach((candidate, index) => {
			const delta = Math.abs(candidate - price);
			if (delta < distance) {
				distance = delta;
				best = index;
			}
		});
		return best;
	};

	const top = rowOf(Math.max(bar.open, bar.close));
	const bottom = rowOf(Math.min(bar.open, bar.close));
	const wickTop = rowOf(bar.high);
	const wickBottom = rowOf(bar.low);

	const rows = prices.map((price) => {
		const key = price.toFixed(1);
		const values = bar.rows[key];
		const isPoc = bar.poc === key;
		const winner = isPoc ? (bar.pocSide === 'ask' ? 'ask' : 'bid') : null;

		return `
			<div class="fp-row ${isPoc ? `poc ${winner}` : ''}">
				<span class="bid ${winner === 'bid' ? 'win' : ''}">${values ? values[0] : ''}</span>
				<span class="divider"></span>
				<span class="ask ${winner === 'ask' ? 'win' : ''}">${values ? values[1] : ''}</span>
			</div>`;
	}).join('');

	return `
		<div class="fp-bar ${bar.current ? 'current' : ''}">
			<div class="fp-time">${bar.time}</div>
			<div class="fp-body">

				<div class="fp-candle" style="height:calc(var(--row) * ${prices.length})">
					<span class="wick" style="top:calc(var(--row) * ${wickTop}); height:calc(var(--row) * ${wickBottom - wickTop + 1})"></span>
					<span class="body ${bar.close >= bar.open ? 'up' : 'down'}"
					      style="top:calc(var(--row) * ${top}); height:calc(var(--row) * ${Math.max(bottom - top, 0.35)})"></span>
				</div>

				<div class="fp-rows">${rows}</div>
			</div>

			<div class="fp-ballast ${bar.ballast ? (bar.ballast.change > 0 ? 'up' : bar.ballast.change < 0 ? 'down' : 'flat') : 'none'}">
				${bar.ballast ? `${bar.ballast.change > 0 ? '+' : ''}${Math.round(bar.ballast.change)}` : ''}
			</div>
		</div>`;
}
