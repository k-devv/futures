/*
================================================================================
 pages/tape/components/summary.js
================================================================================
 WHAT   : The four numbers of the current minute: price, volume, delta, trades.
 WHY    : These are the only facts the tape can give before any bucketing. If
          they are wrong, every footprint row above them would be wrong too.
 WHERE  : app/pages/tape/components
 SCALE  : A number that is not from the tape does not belong in this card.
================================================================================
*/

const f2 = (value) => (Number.isFinite(value) ? value.toFixed(2) : '-');
const f4 = (value) => (Number.isFinite(value) ? value.toFixed(2) : '-');

export default function summary() {
	return `
		<section class="card">
			<div class="flex items-center justify-between">
				<span class="text-micro text-subtle">LIVE TAPE</span>
				<span id="tape-status" class="badge badge-neutral">connecting</span>
			</div>

			<div class="mt-3 flex items-baseline justify-between">
				<p class="text-hero" id="tape-price">-</p>
				<p class="text-micro text-subtle" id="tape-minute">-</p>
			</div>

			<div class="mt-4 grid grid-cols-3 gap-3">
				<div>
					<p class="text-micro text-subtle">volume</p>
					<p class="text-title mt-1" id="tape-volume">-</p>
				</div>
				<div>
					<p class="text-micro text-subtle">delta</p>
					<p class="text-title mt-1" id="tape-delta">-</p>
				</div>
				<div>
					<p class="text-micro text-subtle">trades</p>
					<p class="text-title mt-1" id="tape-trades">-</p>
				</div>
			</div>
		</section>`;
}

summary.paint = (element, state) => {
	const price = element.querySelector('#tape-price');
	const volume = element.querySelector('#tape-volume');
	const delta = element.querySelector('#tape-delta');
	const trades = element.querySelector('#tape-trades');
	const status = element.querySelector('#tape-status');
	const minute = element.querySelector('#tape-minute');

	if (!price) {
		return;
	}

	price.textContent = state.price ? f2(state.price) : '-';
	volume.textContent = state.volume ? f4(state.volume) : '-';
	trades.textContent = String(state.trades || 0);

	delta.textContent = `${state.delta > 0 ? '+' : ''}${f2(state.delta)}`;
	delta.className = `text-title mt-1 ${state.delta > 0 ? 'text-success' : state.delta < 0 ? 'text-danger' : 'text-dim'}`;

	status.className = `badge ${state.connected ? 'badge-success' : 'badge-danger'}`;
	status.textContent = state.connected ? 'live' : 'silent';

	minute.textContent = state.minute
		? new Date(state.minute).toLocaleTimeString('en-GB', { hour12: false }).slice(0, 5)
		: '-';
};

summary.offline = (element) => {
	const status = element.querySelector('#tape-status');
	if (status) {
		status.className = 'badge badge-danger';
		status.textContent = 'offline';
	}
};
