/*
================================================================================
 pages/footprint/components/column.js
================================================================================
 WHAT   : One 5m bar inside the footprint grid: a bid x ask cell per 0.1 price
          row, with the POC marked on the side that won.
 WHY    : The candle lives in the panel above; the grid is only the trade fight.
 WHERE  : app/pages/footprint/components
 SCALE  : Pure function: bar in, HTML out. No DOM lookups, no state.
================================================================================
*/

export default function column(bar, prices) {
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
			<div class="fp-rows">${rows}</div>
		</div>`;
}
