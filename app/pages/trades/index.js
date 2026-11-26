/*
================================================================================
 pages/trades/index.js  -  the Trades page
================================================================================
 WHAT   : The page entry: one component, mounted.
 WHY    : When fills arrive, this page becomes a list instead of a table body;
          the entry does not change.
 WHERE  : app/pages/trades
 SCALE  : New piece -> ./components, one import here.
================================================================================
*/

import fills from './components/fills.js';

export default {
	title: 'Trades',

	mount(element) {
		element.innerHTML = `
			<div class="page-enter">
				${fills()}
			</div>`;
	},
};
