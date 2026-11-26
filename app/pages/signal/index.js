/*
================================================================================
 pages/signal/index.js  -  the Signal page
================================================================================
 WHAT   : The page entry. It mounts three small components and nothing else.
 WHY    : A page file should read like a table of contents. All real work lives
          in ./components, so this stays a dozen lines forever.
 WHERE  : app/pages/signal
 SCALE  : New piece -> new file in components/, one import here.
================================================================================
*/

import state from './components/state.js';
import levels from './components/levels.js';
import plan from './components/plan.js';

export default {
	title: 'Signal',

	mount(element) {
		element.innerHTML = `
			<div class="page-enter flex flex-col gap-4">
				${state()}
				${levels()}
				${plan()}
			</div>`;
	},
};
