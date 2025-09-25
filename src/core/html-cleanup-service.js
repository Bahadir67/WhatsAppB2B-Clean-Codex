const fs = require('fs');
const path = require('path');

class HTMLCleanupService {
    constructor(directory, maxAgeMinutes, intervalMinutes) {
        this.directory = directory;
        this.maxAgeMinutes = maxAgeMinutes;
        this.intervalMinutes = intervalMinutes;
        this.isRunning = false;
        this.intervalHandle = null;
        this.totalCleaned = 0;
    }

    start() {
        if (this.isRunning) {
            return;
        }

        if (!this.directory) {
            console.warn('[CLEANUP] Skipping start - directory not configured');
            return;
        }

        this.isRunning = true;
        console.log(`[CLEANUP] Service started. Directory: ${this.directory}, interval: ${this.intervalMinutes} minutes, max age: ${this.maxAgeMinutes} minutes`);

        // Run first cleanup immediately, then on interval
        this._runCleanup();
        this.intervalHandle = setInterval(() => this._runCleanup(), this.intervalMinutes * 60 * 1000);
    }

    stop() {
        if (this.intervalHandle) {
            clearInterval(this.intervalHandle);
            this.intervalHandle = null;
        }

        this.isRunning = false;
        console.log('[CLEANUP] Service stopped');
    }

    async _runCleanup() {
        const cutoff = Date.now() - this.maxAgeMinutes * 60 * 1000;
        let cleanedCount = 0;

        try {
            if (!fs.existsSync(this.directory)) {
                console.warn(`[CLEANUP] Directory not found: ${this.directory}`);
                return;
            }

            const files = await fs.promises.readdir(this.directory);

            await Promise.all(files.map(async (file) => {
                if (!file.endsWith('.html')) {
                    return;
                }

                const filePath = path.join(this.directory, file);

                try {
                    const stats = await fs.promises.stat(filePath);
                    const modifiedTime = stats.mtime.getTime();

                    if (modifiedTime < cutoff) {
                        await fs.promises.unlink(filePath);
                        cleanedCount += 1;
                        console.log(`[CLEANUP] Deleted stale file: ${file}`);
                    }
                } catch (error) {
                    console.error(`[CLEANUP] Failed to process ${file}:`, error.message);
                }
            }));

            if (cleanedCount > 0) {
                this.totalCleaned += cleanedCount;
                console.log(`[CLEANUP] Removed ${cleanedCount} stale file(s). Total cleaned: ${this.totalCleaned}`);
            } else {
                console.log('[CLEANUP] No stale HTML files found');
            }
        } catch (error) {
            console.error('[CLEANUP] Cleanup run failed:', error.message);
        }
    }

    getStats() {
        return {
            isRunning: this.isRunning,
            totalCleaned: this.totalCleaned,
            config: {
                maxAgeMinutes: this.maxAgeMinutes,
                intervalMinutes: this.intervalMinutes
            }
        };
    }

    triggerCleanup() {
        if (!this.isRunning) {
            console.warn('[CLEANUP] Trigger requested while service stopped - running single cleanup');
        }

        return this._runCleanup();
    }
}

module.exports = HTMLCleanupService;
