function TimingPoint(line)
{
    var data = line.split(',');
    if (data.length < 2)
    {
        throw 'invalid data';
    }

    this.time = data[0] | 0;
    this.beatLength = +data[1];
    this.meter = (data[2] | 0) || 4;
    var effects = data[7] | 0;
    this.kiai = effects & 1;
    this.omitFirstBarLine = !!(effects & 8);

    // this is non-inherited timingPoint
    if (this.beatLength >= 0)
    {
        // osu!stable constrains uninherited timing points to this range.
        // Gimmick maps sometimes store values such as 1E-300; applying those
        // literally makes the accumulated taiko scroll overflow.
        this.beatLength = Math.max(6, Math.min(this.beatLength, 60000));
        TimingPoint.parent = this;
        this.sliderVelocity = 1;
    }
    else
    {
        this.parent = TimingPoint.parent;
        this.sliderVelocity = -100 / this.beatLength;
        this.beatLength = this.parent.beatLength / this.sliderVelocity;
        this.meter = this.parent.meter;
    }
}
Object.defineProperties(TimingPoint.prototype, {
    bpm: {
        get: function()
        {
            return 60000 / this.beatLength;
        }
    }
});
