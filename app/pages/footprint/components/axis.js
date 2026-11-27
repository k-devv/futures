/*
================================================================================
 pages/footprint/components/axis.js
================================================================================
 WHAT   : The shared price axis. One column of prices, 0.1 apart, high to low.
 WHY    : Every bar must sit on the same prices, or the chart lies about where
          the fight happened.
 WHERE  : app/pages/footprint/components
 SCALE  : Pure function: prices in, HTML out.
================================================================================
*/

export default function axis(prices) {
	return `
		<div class="fp-axis" style="--rows:${prices.length}">
			<div class="fp-head-cell"></div>
			${prices.map(price => `<div class="fp-price">${price.toFixed(1)}</div>`).join('')}
		</div>`;
}
