import {tileLayer} from './map';

document.addEventListener('DOMContentLoaded', () => {
    // Color Filter Controls
    const tilePane = tileLayer.getContainer();
    const colorPresets = document.getElementById('color-presets');
    const hueSlider = document.getElementById('hue-slider');
    const sepiaSlider = document.getElementById('sepia-slider');
    const saturateSlider = document.getElementById('saturate-slider');
    const brightnessSlider = document.getElementById('brightness-slider');
    const resetButton = document.getElementById('reset-filters');

    const hueValue = document.getElementById('hue-value');
    const sepiaValue = document.getElementById('sepia-value');
    const saturateValue = document.getElementById('saturate-value');
    const brightnessValue = document.getElementById('brightness-value');

    function updateFilter() {
        const hue = hueSlider.value;
        const sepia = sepiaSlider.value;
        const saturate = saturateSlider.value;
        const brightness = brightnessSlider.value;

        hueValue.textContent = `${hue}deg`;
        sepiaValue.textContent = `${sepia}%`;
        saturateValue.textContent = `${saturate}%`;
        brightnessValue.textContent = `${brightness}%`;

        // The order of CSS filters is important.
        // 1. sepia() introduces color. This is necessary for hue-rotate and saturate to work on grayscale images.
        // 2. saturate() adjusts the intensity of the new color.
        // 3. hue-rotate() shifts the color.
        // 4. brightness() adjusts the overall lightness/darkness.
        tilePane.style.filter = `sepia(${sepia}%) saturate(${saturate}%) hue-rotate(${hue}deg) brightness(${brightness}%)`;
    }


    function resetFilters() {
        hueSlider.value = 0;
        sepiaSlider.value = 0;
        saturateSlider.value = 100;
        brightnessSlider.value = 100;
        colorPresets.value = 'none';
        updateFilter();
    }

    colorPresets.addEventListener('change', (e) => {
        const selectedFilter = e.target.value;
        if (selectedFilter === 'none') {
            resetFilters();
            return;
        }

        // Default values
        const filterValues = {
            'hue-rotate': 0,
            'sepia': 0,
            'saturate': 100,
            'brightness': 100
        };

        selectedFilter.split(' ').forEach(filter => {
            const property = filter.substring(0, filter.indexOf('('));
            const value = filter.substring(filter.indexOf('(') + 1, filter.indexOf(')'));

            switch (property) {
                case 'hue-rotate':
                    filterValues[property] = parseInt(value); // e.g., "90deg" -> 90
                    break;
                case 'sepia':
                    filterValues[property] = parseFloat(value); // e.g., "100%" -> 100
                    break;
                case 'saturate':
                case 'brightness':
                    const numericValue = parseFloat(value);
                    if (value.includes('%')) {
                        filterValues[property] = numericValue;
                    } else {
                        filterValues[property] = numericValue * 100;
                    }
                    break;
            }
        });

        hueSlider.value = filterValues['hue-rotate'];
        sepiaSlider.value = filterValues['sepia'];
        saturateSlider.value = filterValues['saturate'];
        brightnessSlider.value = filterValues['brightness'];

        updateFilter();
    });


    hueSlider.addEventListener('input', updateFilter);
    sepiaSlider.addEventListener('input', updateFilter);
    saturateSlider.addEventListener('input', updateFilter);
    brightnessSlider.addEventListener('input', updateFilter);
    resetButton.addEventListener('click', resetFilters);

    // Initial filter update
    updateFilter();
});