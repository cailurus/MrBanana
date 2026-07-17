/**
 * Mr. Banana - Jable.tv Cookie Extractor
 * 
 * Copy and paste this entire script into the browser console (F12 → Console)
 * while on jable.tv (any page, must be logged in).
 * It will copy the cookie string to your clipboard, ready to paste into
 * Mr. Banana's Web UI → Download Settings → Jable Cookie field.
 * 
 * Usage:
 *   1. Open jable.tv in Chrome (logged in)
 *   2. Press F12 to open DevTools → Console tab
 *   3. Paste this entire script and press Enter
 *   4. The cookie string is now in your clipboard!
 */

(function() {
    const cookies = document.cookie;
    if (!cookies) {
        alert('❌ No cookies found. Are you on jable.tv?');
        return;
    }

    // Copy to clipboard
    navigator.clipboard.writeText(cookies).then(() => {
        console.log('✅ Jable.tv cookies copied to clipboard!');
        console.log('──────────────────────────────────────────────');
        console.log('Cookie string:');
        console.log(cookies);
        console.log('──────────────────────────────────────────────');
        console.log('');
        console.log('Next steps:');
        console.log('1. Go to Mr. Banana Web UI → Download Settings');
        console.log('2. Paste into "Jable Cookie" field');
        console.log('3. Click Save');
        console.log('');
        console.log('Key cookies found:');

        // Highlight important cookies
        const pairs = cookies.split(';').map(s => s.trim());
        const important = ['cf_clearance', '__cf_bm', 'PHPSESSID'];
        for (const key of important) {
            const found = pairs.find(p => p.startsWith(key + '='));
            if (found) {
                console.log(`  ✅ ${found.split('=')[0]} = ${found.split('=')[1].substring(0, 30)}...`);
            } else {
                console.log(`  ⚠️ ${key} = NOT FOUND (may not be needed)`);
            }
        }
        alert('✅ Cookie copied to clipboard!\n\nPaste it in Mr. Banana → Download Settings → Jable Cookie');
    }).catch(err => {
        console.error('Failed to copy:', err);
        // Fallback: show in console
        console.log('⚠️ Clipboard access denied. Copy this manually:');
        console.log(cookies);
        alert('⚠️ Could not copy automatically.\n\nPlease manually copy the cookie string from the console output (F12 → Console).');
    });
})();