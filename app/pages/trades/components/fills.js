/*
================================================================================
 pages/trades/components/fills.js
================================================================================
 WHAT   : The fills table: time, side, price, qty, net.
 WHY    : Every row is a real fill from the exchange; nothing is computed here
          beyond what the row already says.
 WHERE  : app/pages/trades/components
 SCALE  : Rows are passed in already formatted; this file only lays them out.
================================================================================
*/

/**
 * @param {{ rows?: Array<{time:string, side:string, price:string, qty:string, net:string, tone?:string}> }} data
 */
export default function fills({ rows = [] } = {}) {
	const body = rows.length
		? rows.map(row => `
			<tr>
				<td>${row.time}</td>
				<td class="text-${row.tone || 'dim'}">${row.side}</td>
				<td class="num">${row.price}</td>
				<td class="num">${row.qty}</td>
				<td class="num text-${row.tone || 'dim'}">${row.net}</td>
			</tr>`).join('')
		: '<tr><td colspan="5" class="text-micro text-subtle">no trades yet</td></tr>';

	return `
		<div class="card p-0">
			<table class="table">
				<thead>
					<tr>
						<th>TIME</th><th>SIDE</th><th class="num">PRICE</th>
						<th class="num">QTY</th><th class="num">NET</th>
					</tr>
				</thead>
				<tbody id="trades-body">${body}</tbody>
			</table>
		</div>`;
}
