function Taiko(osu)
{
    Scroll.call(this, osu);

    for (var i = 0; i < this.HitObjects.length; i++)
    {
        var hitObject = this.HitObjects[i];
        hitObject.position.x = hitObject.time;
        hitObject.endPosition.x = hitObject.endTime;
    }

    // osu!taiko uses overlapping scrolling: every object keeps the velocity
    // active at its own start time. Rebuild bar lines as timestamps instead of
    // using Scroll's sequential, accumulated positions.
    this.barLines = [];
    var endTime = (this.HitObjects.length ? this.HitObjects[this.HitObjects.length - 1].endTime : 0) + 1;
    var timingPoints = this.TimingPoints.filter(function(timingPoint)
    {
        return !timingPoint.parent;
    });
    for (var timingPointIndex = 0; timingPointIndex < timingPoints.length; timingPointIndex++)
    {
        var timingPoint = timingPoints[timingPointIndex];
        var barLength = timingPoint.beatLength * timingPoint.meter;
        var barLineLimit = timingPoints[timingPointIndex + 1]
            ? timingPoints[timingPointIndex + 1].time
            : endTime;
        for (var barTime = timingPoint.time; barTime < barLineLimit; barTime += barLength)
        {
            this.barLines.push(barTime);
        }
    }
}
Taiko.prototype = Object.create(Scroll.prototype, {

});
Taiko.prototype.constructor = Taiko;
Taiko.prototype.hitObjectTypes = {};
Taiko.ID = 1;
Beatmap.modes[Taiko.ID] = Taiko;
Taiko.DEFAULT_COLORS = [
    '#eb452c',
    '#438eac',
    '#fcb806'
];
Taiko.DIAMETER = 56;
Taiko.PLAYFIELD_LENGTH = Beatmap.WIDTH - 160;
Taiko.BASE_SCROLL_SPEED = 0.14;
Taiko.prototype.scrollMultiplierAt = function(time)
{
    var timingPoint = this.timingPointAt(time);
    return this.SliderMultiplier * 1000 / timingPoint.beatLength;
};
Taiko.prototype.calcX = function(time, currentTime, originTime)
{
    var multiplier = this.scrollMultiplierAt(
        typeof originTime == 'undefined' ? time : originTime
    );
    return (time - currentTime) * Taiko.BASE_SCROLL_SPEED * multiplier;
};
Taiko.prototype.update = function(ctx)
{
    ctx.shadowColor = '#666';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.translate(160, 200);
};
Taiko.prototype.draw = function(time, ctx)
{
    if (typeof this.tmp.first == 'undefined')
    {
        this.tmp.first = 0;
        this.tmp.barLine = 0;
    }

    var scroll = time;
    while (this.tmp.first < this.HitObjects.length &&
        time > this.HitObjects[this.tmp.first].endTime)
    {
        this.tmp.first++;
    }
    while (this.tmp.barLine < this.barLines.length &&
        this.calcX(this.barLines[this.tmp.barLine], scroll) < -Taiko.DIAMETER)
    {
        this.tmp.barLine++;
    }
    for (var i = this.tmp.barLine; i < this.barLines.length; i++)
    {
        var barLine = this.calcX(this.barLines[i], scroll);
        if (barLine > Taiko.PLAYFIELD_LENGTH)
        {
            continue;
        }
        ctx.beginPath();
        ctx.moveTo(barLine, -Taiko.DIAMETER);
        ctx.lineTo(barLine, Taiko.DIAMETER);
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
    }
    for (var i = this.HitObjects.length - 1; i >= this.tmp.first; i--)
    {
        var hitObject = this.HitObjects[i];
        if (time > hitObject.endTime)
        {
            continue;
        }
        var startX = this.calcX(hitObject.position.x, scroll);
        var endX = this.calcX(hitObject.endPosition.x, scroll, hitObject.position.x);
        if (startX > Taiko.PLAYFIELD_LENGTH + Taiko.DIAMETER &&
            endX > Taiko.PLAYFIELD_LENGTH + Taiko.DIAMETER)
        {
            continue;
        }
        hitObject.draw(scroll, ctx);
    }
    ctx.clearRect(-160, -200, Taiko.DIAMETER * 2, 400);
};
Taiko.prototype.processBG = function(ctx)
{
    var offset = - Taiko.DIAMETER;
    //ctx.drawImage(ctx.canvas, -160, offset, ctx.canvas.width, ctx.canvas.height);
    //ctx.beginPath();
    //ctx.rect(0, 0, Beatmap.WIDTH, offset);
    //ctx.fillStyle = '#000';
    //ctx.fill();

    // rail
    ctx.beginPath();
    ctx.rect(-160, offset, Beatmap.WIDTH, Taiko.DIAMETER * 2);
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 8;
    ctx.stroke();
    ctx.fillStyle = '#000';
    ctx.fill();

    // drum
    ctx.beginPath();
    ctx.rect(-160, offset, Taiko.DIAMETER * 2, Taiko.DIAMETER * 2);
    ctx.fillStyle = '#ff0080';
    ctx.fill();

    var border = 6;
    ctx.beginPath();
    ctx.arc(0, 0, Taiko.DIAMETER / 2, -Math.PI, Math.PI);
    ctx.fillStyle = 'rgba(255,255,255,.2)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.2)';
    ctx.lineWidth = border;
    ctx.stroke();
};
