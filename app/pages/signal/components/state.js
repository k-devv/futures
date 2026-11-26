/*
================================================================================
 pages/signal/components/state.js
================================================================================
 WHAT   : The one word that matters: WAIT, BUY, SELL, SKIP.
 WHY    : The state is the whole page in a glance; everything else explains it.
 WHERE  : app/pages/signal/components
 SCALE  : Keep it a pure function of the data it is given.
================================================================================
*/

/**
 * @param {{ word?: string, tone?: string, note?: string }} state
 *   word: WAIT | BUY | SELL | SKIP, tone: neutral | success | danger | warning
 */
export default function state({ word = 'WAIT', tone = 'neutral', note = 'no signal yet' } = {}) {
	return `
		<section class="card">
			<div class="flex items-center justify-between">
				<span class="text-micro text-subtle">STATE</span>
				<span class="badge badge-${tone}" id="state-badge">waiting</span>
			</div>
			<p class="text-hero mt-3" id="state-word">${word}</p>
			<p class="text-meta text-dim mt-2" id="state-note">${note}</p>
		</section>`;
}
