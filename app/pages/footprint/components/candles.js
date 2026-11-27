/*
================================================================================
 pages/footprint/components/candles.js
================================================================================
 WHAT   : The candle panel above the footprint. One cell per bar, same column
          width as the footprint below, so the two line up.
 WHY    : Candles and price rows fight for the same vertical space when they share
          one grid. Separated, the candles show direction and the footprint shows
          the fight - each with its own scale.
 WHERE  : app/pages/footprint/components
 SCALE  : Pure function: bar, low, high -> HTML.
================================================================================
*/

export default function candles(bar, low, high) {
	const span = high - low || 1;
	const top = ((high - Math.max(bar.open, bar.close)) / span) * 100;
	const body = (Math.abs(bar.close - bar.open) / span) * 100;
	const wickTop = ((high - bar.high) / span) * 100;
	const wickBottom = ((high - bar.low) / span) * 100;

	return `
		<div class="fp-candle-cell ${bar.current ? 'current' : ''}">
			<span class="wick" style="top:${wickTop}%; height:${Math.max(wickBottom - wickTop, 0.6)}%"></span>
			<span class="body ${bar.close >= bar.open ? 'up' : 'down'}"
			      style="top:${top}%; height:${Math.max(body, 0.8)}%"></span>
		</div>`;
}
