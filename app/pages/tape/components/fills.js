/*
================================================================================
 pages/tape/components/fills.js
================================================================================
 WHAT   : The last fills, newest first: time, side, price, size.
 WHY    : This is the tape with nothing added. Every later view (footprint rows,
          absorption, POC) is a rearrangement of exactly these numbers.
 WHERE  : app/pages/tape/components
 SCALE  : 80 rows is enough to see the rhythm; the list is capped server-side.
================================================================================
*/

const time = (ms) => {
	const date = new Date(ms);
	const clock = date.toLocaleTimeString('en-GB', { hour12: false });
	return `${clock}.${String(date.getMilliseconds()).padStart(3, '0')}`;
};

export default function fills() {
	return `
		<div class="card p-0">
			<table class="table">
				<thead>
					<tr>
						<th>TIME</th>
						<th>SIDE</th>
						<th class="num">PRICE</th>
						<th class="num">SIZE</th>
					</tr>
				</thead>
				<tbody id="tape-fills">
					<tr><td colspan="4" class="text-micro text-subtle">waiting for the first fill</td></tr>
				</tbody>
			</table>
		</div>`;
}

fills.paint = (element, state) => {
	const body = element.querySelector('#tape-fills');
	if (!body || !state.list || !state.list.length) {
		return;
	}

	body.innerHTML = state.list.slice(0, 40).map((fill) => {
		const buy = fill.side === 'buy';
		return `
			<tr>
				<td class="text-micro text-subtle">${time(fill.ms)}</td>
				<td class="${buy ? 'text-success' : 'text-danger'}">${buy ? 'BUY' : 'SELL'}</td>
				<td class="num">${fill.price.toFixed(2)}</td>
				<td class="num">${fill.qty.toFixed(2)}</td>
			</tr>`;
	}).join('');
};
