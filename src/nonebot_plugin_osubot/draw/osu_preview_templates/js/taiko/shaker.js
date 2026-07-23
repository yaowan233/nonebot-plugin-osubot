function Shaker(data, beatmap)
{
    Spinner.call(this, data, beatmap);

    var difficulty = beatmap.OverallDifficulty;
    var hitsPerSecond;
    if (difficulty > 5)
    {
        hitsPerSecond = 5 + (7.5 - 5) * (difficulty - 5) / 5;
    }
    else
    {
        hitsPerSecond = 3 + (5 - 3) * difficulty / 5;
    }
    this.requiredHits = Math.max(1, Math.floor(this.duration / 1000 * hitsPerSecond * 1.65));
}
Shaker.prototype = Object.create(Spinner.prototype, {});
Shaker.prototype.constructor = Shaker;
Shaker.ID = 8;
Taiko.prototype.hitObjectTypes[Shaker.ID] = Shaker;
Shaker.prototype.draw = function(scroll, ctx)
{
    var x = Math.max(0, this.beatmap.calcX(this.position.x, scroll));
    var diam = Taiko.DIAMETER;
    var border = 3;
    var elapsed = scroll - this.position.x;

    // osu!taiko's swell stays at the hit target and displays an expanding
    // target ring shortly after it starts. It is not the standard ruleset's
    // full-screen spinner.
    if (elapsed >= 100)
    {
        var ringProgress = Math.min((elapsed - 100) / 400, 1);
        var easedProgress = 1 - Math.pow(1 - ringProgress, 5);
        var ringScale = 1 + 4 * easedProgress;

        ctx.beginPath();
        ctx.arc(x, 0, diam / 2 * ringScale, -Math.PI, Math.PI);
        ctx.strokeStyle = 'rgba(252,184,6,.28)';
        ctx.lineWidth = 4;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(x, 0, diam / 2 * ringScale - 3, -Math.PI, Math.PI);
        ctx.strokeStyle = 'rgba(255,255,255,.75)';
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(x, 0, diam / 2 - border / 2, -Math.PI, Math.PI);
    ctx.fillStyle = Taiko.DEFAULT_COLORS[2];
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = border;
    ctx.stroke();

    // A GIF preview has no player input, so advance the counter at the ideal
    // rate to communicate how many alternating hits the swell requires.
    var completion = Math.max(0, Math.min(elapsed / this.duration, 1));
    var remainingHits = this.requiredHits - Math.floor(this.requiredHits * completion);

    ctx.save();
    ctx.translate(x, 0);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold ' + (remainingHits >= 100 ? 18 : 22) + 'px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = 'rgba(80,50,0,.8)';
    ctx.shadowBlur = 2;
    ctx.fillText(remainingHits, 0, 1);
    ctx.restore();
};
