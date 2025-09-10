import { marked } from 'marked';
import DOMPurify from 'dompurify';

document.addEventListener('DOMContentLoaded', () => {
    // Changelog
    const changelogPopup = document.getElementById('changelog-popup');
    const changelogList = document.getElementById('changelog-list');
    const closePopupButton = document.getElementById('close-popup');

    const showChangelogPopup = (content) => {
        changelogList.innerHTML = DOMPurify.sanitize(marked.parse(content));
        changelogPopup.classList.remove('hidden');
    };

    const hideChangelogPopup = () => {
        changelogPopup.classList.add('hidden');
    };

    const checkChangelog = async () => {
        try {
            const response = await fetch('/dist/changelog.json');
            const data = await response.json();
            const latestData = data[0];
            const currentVersion = latestData.version;
            const lastSeenVersion = localStorage.getItem('lastSeenChangelogVersion');

            if (currentVersion !== lastSeenVersion) {
                let changelogContent = '';
                const recentChangelogs = data.slice(0, 5);

                recentChangelogs.forEach(release => {
                    changelogContent += `## ${release.version}\n\n${release.notes}\n\n---\n\n`;
                });

                changelogContent += 'For a full list of changes, please visit the [GitHub releases page](https://github.com/TheodorCrosswell/KJV_Search_Tools/releases).\n';
                
                showChangelogPopup(changelogContent);
                localStorage.setItem('lastSeenChangelogVersion', currentVersion);
            }
        } catch (error) {
            console.error('Failed to fetch changelog:', error);
        }
    };

    closePopupButton.addEventListener('click', hideChangelogPopup);
    checkChangelog();
});