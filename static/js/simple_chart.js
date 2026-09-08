/*
 * simple_chart.js
 * ---------------
 * Draws a very simple bar chart on the admin dashboard showing how
 * many books exist in each category. Written by hand with the
 * HTML5 Canvas API instead of a charting library, so it stays easy
 * to read and explain during evaluation.
 */

document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById("categoryChart");
    if (!canvas || typeof categoryLabels === "undefined" || categoryLabels.length === 0) {
        return;
    }

    const context = canvas.getContext("2d");
    canvas.width = canvas.clientWidth;
    canvas.height = 220;

    const chartHeight = canvas.height - 40;
    const barCount = categoryLabels.length;
    const barWidth = Math.min(70, (canvas.width - 40) / barCount - 16);
    const maxValue = Math.max.apply(null, categoryValues);
    const barColor = "#2f6690";

    context.font = "12px Segoe UI";
    context.fillStyle = "#22303e";

    categoryValues.forEach(function (value, index) {
        const barHeight = maxValue > 0 ? (value / maxValue) * chartHeight : 0;
        const x = 30 + index * (barWidth + 16);
        const y = chartHeight - barHeight + 10;

        context.fillStyle = barColor;
        context.fillRect(x, y, barWidth, barHeight);

        // Value label above the bar
        context.fillStyle = "#22303e";
        context.textAlign = "center";
        context.fillText(value, x + barWidth / 2, y - 6);

        // Category label below the bar
        const label = categoryLabels[index].length > 10
            ? categoryLabels[index].substring(0, 9) + "…"
            : categoryLabels[index];
        context.fillText(label, x + barWidth / 2, chartHeight + 24);
    });
});
