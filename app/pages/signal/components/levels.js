/*
================================================================================
 pages/signal/components/levels.js
================================================================================
 WHAT   : The level under test, the live price, and the delta of the bar.
 WHY    : This is the location check made visible: a balance, its level, and
          who is winning the bar.
 WHERE  : app/pages/signal/components
 SCALE  : Numbers arrive as strings already formatted; this file never formats.
================================================================================
*/

export default function levels({ level = '-', price = '-', delta = 'delta -', note = 'nearest level' } = {}) {
	return `
		<section class="card">
			<div class="flex items-center justify-between">
				<span class="text-micro text-subtle">LEVEL</span>
				<span class="text-micro text-subtle">PRICE</span>
			</div>
			<div class="flex items-baseline justify-between mt-2">
				<div>
					<p class="text-display" id="level">${level}</p>
					<p class="text-micro text-subtle mt-1" id="level-note">${note}</p>
				</div>
				<div class="text-right">
					<p class="text-display" id="price">${price}</p>
					<p class="text-micro text-subtle mt-1" id="delta">${delta}</p>
				</div>
			</div>
		</section>`;
}
