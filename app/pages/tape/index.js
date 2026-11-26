/*
================================================================================
 pages/tape/index.js  -  the tape, exactly as it is
================================================================================
 WHAT   : Shows the live trade stream: the current minute's volume, delta and
          trade count, plus the last fills. Nothing else.
 WHY    : Before any footprint row is drawn, the raw tape has to be visible and
          believable. This page is the proof the socket is alive.
 WHERE  : app/pages/tape
 SCALE  : The page fetches one JSON every 500 ms and redraws. No other logic.
================================================================================
*/

import summary from './components/summary.js';
import fills from './components/fills.js';

const POLL_MS = 500;

export default {
	title: 'Tape',

	mount(element) {
		element.innerHTML = `
			<div class="page-enter flex flex-col gap-4">
				${summary()}
				${fills()}
			</div>`;

		const tick = async () => {
			try {
				const response = await fetch('/api/tape', { cache: 'no-store' });
				const state = await response.json();
				if (element.isConnected) {
					summary.paint(element, state);
					fills.paint(element, state);
				}
			} catch (error) {
				if (element.isConnected) {
					summary.offline(element);
				}
			}
		};

		tick();
		this.timer = setInterval(tick, POLL_MS);
	},

	unmount() {
		clearInterval(this.timer);
	},
};
