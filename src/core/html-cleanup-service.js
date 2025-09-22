// HTML Cleanup Service - Stub file
// This service is currently disabled

class HTMLCleanupService {
    constructor(directory, maxAge, interval) {
        this.directory = directory;
        this.maxAgeMinutes = maxAge;
        this.intervalMinutes = interval;
        this.isRunning = false;
    }
    
    start() {
        console.log('[CLEANUP] Service disabled - using manual cleanup');
        this.isRunning = false;
    }
    
    stop() {
        this.isRunning = false;
    }
    
    getStats() {
        return {
            isRunning: this.isRunning,
            totalCleaned: 0,
            config: {
                maxAgeMinutes: this.maxAgeMinutes,
                intervalMinutes: this.intervalMinutes
            }
        };
    }
    
    triggerCleanup() {
        console.log('[CLEANUP] Manual cleanup triggered (disabled)');
    }
}

module.exports = HTMLCleanupService;