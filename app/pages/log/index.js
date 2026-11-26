/*
================================================================================
 pages/log/index.js  -  the Log page
================================================================================
 WHAT   : The page entry: one component, mounted.
 WHY    : The log is the audit trail - every gate, confirm and order the engine
          took, in the order it took them.
 WHERE  : app/pages/log
 SCALE  : New piece -> ./components, one import here.
================================================================================
*/

import decisions from './components/decisions.js';

export default {
	title: 'Log',

	mount(element) {
		element.innerHTML = `
			<div class="page-enter">
				${decisions()}
			</div>`;
	},
};
