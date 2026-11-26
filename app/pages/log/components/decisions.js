/*
================================================================================
 pages/log/components/decisions.js
================================================================================
 WHAT   : A list of engine decisions: time, what it saw, what it did.
 WHY    : "Why did it not trade" must be answerable without reading the server.
 WHERE  : app/pages/log/components
 SCALE  : Entries arrive formatted; this file lays them out.
================================================================================
*/

/**
 * @param {{ entries?: Array<{time:string, text:string, tone?:string}> }} data
 */
export default function decisions({ entries = [] } = {}) {
	const body = entries.length
		? entries.map(entry => `
			<div class="flex items-baseline gap-3">
				<span class="text-micro text-subtle w-16 shrink-0">${entry.time}</span>
				<span class="text-meta text-${entry.tone || 'dim'}">${entry.text}</span>
			</div>`).join('')
		: '<p class="text-meta text-dim">every gate, confirm and order appears here</p>';

	return `
		<div class="card">
			<p class="text-micro text-subtle">DECISIONS</p>
			<div id="log-body" class="mt-3 flex flex-col gap-2">${body}</div>
		</div>`;
}
