const fs = require('fs');
const path = require('path');

const defaultWhatsappPhone = process.env.WHATSAPP_PHONE;
const defaultWhatsappNumber = defaultWhatsappPhone ? `${defaultWhatsappPhone}@c.us` : null;

class HTMLCleanupService {
    constructor(directory, maxAgeMinutes, intervalMinutes) {
        this.directory = directory;
        this.maxAgeMinutes = maxAgeMinutes;
        this.intervalMinutes = intervalMinutes;
        this.isRunning = false;
        this.intervalHandle = null;
        this.totalCleaned = 0;
        this.lastRunAt = null;
        this.lastRunDeleted = 0;
        this.lastRunError = null;
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

            this.lastRunDeleted = cleanedCount;
            this.lastRunError = null;
        } catch (error) {
            console.error('[CLEANUP] Cleanup run failed:', error.message);
            this.lastRunError = error.message;
        }

        this.lastRunAt = new Date();
    }

    getStats() {
        return {
            isRunning: this.isRunning,
            totalCleaned: this.totalCleaned,
            lastRunAt: this.lastRunAt ? this.lastRunAt.toISOString() : null,
            lastRunDeleted: this.lastRunDeleted,
            lastRunError: this.lastRunError,
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

    async listCatalogFiles() {
        if (!this.directory) {
            return [];
        }

        if (!fs.existsSync(this.directory)) {
            return [];
        }

        const now = Date.now();
        const cutoff = now - this.maxAgeMinutes * 60 * 1000;
        const files = await fs.promises.readdir(this.directory);
        const htmlFiles = files.filter((file) => file.endsWith('.html'));

        const entries = await Promise.all(htmlFiles.map(async (file) => {
            const filePath = path.join(this.directory, file);

            try {
                const stats = await fs.promises.stat(filePath);
                const modifiedTime = stats.mtime.getTime();
                const ageMinutes = (now - modifiedTime) / (60 * 1000);
                const parsed = HTMLCleanupService.parseCatalogFilename(file);

                return {
                    filename: file,
                    whatsappNumber: parsed?.whatsappNumber || null,
                    sessionId: parsed?.sessionId || null,
                    catalogTimestamp: parsed?.timestamp || null,
                    sizeBytes: stats.size,
                    modifiedAt: stats.mtime.toISOString(),
                    ageMinutes: Number(ageMinutes.toFixed(1)),
                    stale: modifiedTime < cutoff
                };
            } catch (error) {
                return {
                    filename: file,
                    error: error.message
                };
            }
        }));

        return entries.sort((a, b) => {
            if (!a.modifiedAt) {
                return 1;
            }

            if (!b.modifiedAt) {
                return -1;
            }

            return new Date(b.modifiedAt) - new Date(a.modifiedAt);
        });
    }

    static parseCatalogFilename(filename) {
        try {
            if (!filename.startsWith('products_') || !filename.endsWith('.html')) {
                return null;
            }

            const parts = filename.replace('.html', '').split('_');

            if (parts.length === 2) {
                return {
                    whatsappNumber: defaultWhatsappNumber,
                    sessionId: parts[1],
                    timestamp: null,
                    legacy: true
                };
            }

            if (parts.length === 4) {
                const timestamp = Number(parts[3]);

                return {
                    whatsappNumber: `${parts[1]}@c.us`,
                    sessionId: parts[2],
                    timestamp: Number.isNaN(timestamp) ? null : timestamp,
                    legacy: false
                };
            }

            return null;
        } catch (error) {
            console.error(`[CLEANUP] Failed to parse filename ${filename}:`, error.message);
            return null;
        }
    }
}

module.exports = HTMLCleanupService;
