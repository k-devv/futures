/*
================================================================================
 pages/signal/components/plan.js
================================================================================
 WHAT   : What the trade would be: stop, target, risk in shillings.
 WHY    : A signal without a stop and a target is an opinion. This is the plan
          before anything is sent.
 WHERE  : app/pages/signal/components
 SCALE  : Three slots, no more. A fourth number means a different component.
================================================================================
*/

export default function plan({ stop = '-', target = '-', risk = '-' } = {}) {
	return `
		<section class="card">
			<p class="text-micro text-subtle">PLAN</p>
			<div class="mt-3 grid grid-cols-3 gap-3">
				<div><p class="text-micro text-subtle">stop</p><p class="text-title mt-1" id="stop">${stop}</p></div>
				<div><p class="text-micro text-subtle">target</p><p class="text-title mt-1" id="target">${target}</p></div>
				<div><p class="text-micro text-subtle">risk</p><p class="text-title mt-1" id="risk">${risk}</p></div>
			</div>
		</section>`;
}
