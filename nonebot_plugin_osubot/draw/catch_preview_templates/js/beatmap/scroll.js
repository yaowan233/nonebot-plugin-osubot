function Scroll(osu)
{
    Beatmap.call(this, osu);

    // dp for numerous call to this.scrollAt
    this.scrollAtTimingPointIndex = [ 0 ];
    var currentIdx = this.timingPointIndexAt(0),
        current = this.TimingPoints[currentIdx],
        base = this.TimingPoints[0],
        scrollVelocity = base.beatLength / current.beatLength;
    this.scrollAtTimingPointIndex[currentIdx] = current.time * scrollVelocity;
    while (++currentIdx < this.TimingPoints.length)
    {
        var next = this.TimingPoints[currentIdx];
        this.scrollAtTimingPointIndex[currentIdx] = (next.time - current.time) * scrollVelocity +
            this.scrollAtTimingPointIndex[currentIdx - 1];
        current = next;
        scrollVelocity = base.beatLength / current.beatLength;
    }

    this.barLines = [];
    var endTime = (this.HitObjects.length ? this.HitObjects[this.HitObjects.length - 1].endTime : 0) + 1;
    for (var i = 0; i < this.TimingPoints.length; i++)
    {
        var current = this.TimingPoints[i],
            base = current.parent || current,
            barLength = base.beatLength * base.meter,
            next = this.TimingPoints[i + 1],
            barLineLimit = next ? (next.parent || next).time : endTime;
        for (var barTime = base.time; barTime < barLineLimit; barTime += barLength)
        {
            this.barLines.push(this.scrollAt(barTime));
        }
    }
}
Scroll.prototype = Object.create(Beatmap.prototype);
Scroll.prototype.constructor = Scroll;
Scroll.prototype.scrollAt = function(time)
{
    var currentIdx = this.timingPointIndexAt(time),
        current = this.TimingPoints[currentIdx],
        base = this.TimingPoints[0],
        scrollVelocity = base.beatLength / current.beatLength;
    return (time - current.time) * scrollVelocity + this.scrollAtTimingPointIndex[currentIdx];
};
