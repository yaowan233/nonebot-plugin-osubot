function Beatmap(osu)
{
    // for temporary vars that need for drawing
    this.tmp = {};

    // [General]
    this.StackLeniency = 0.7;
    this.PreviewTime = -1;

    // [Metadata]
    this.Title = '';
    this.TitleUnicode = undefined;
    this.Artist = '';
    this.ArtistUnicode = undefined;
    this.Creator = '';
    this.Version = undefined;

    // [Difficulty]
    this.CircleSize = 5;
    this.OverallDifficulty = 5;
    this.ApproachRate = undefined;
    this.SliderMultiplier = 1.4;
    this.SliderTickRate = 1;

    // [TimingPoints]
    this.TimingPoints = [];

    // [Colours]
    this.Colors = [];

    // [HitObjects]
    this.HitObjects = [];


    var stream = osu.replace(/\r\n?/g, '\n').split('\n').reverse(),
        currentSection, line;
    while (typeof (line = stream.pop()) != 'undefined')
    {
        // skip comments
        if (/^\/\//.test(line))
        {
            continue;
        }

        if (/^\[/.test(line))
        {
            currentSection = line.slice(1, line.indexOf(']'));
            continue;
        }

        switch (currentSection)
        {
            case 'General':
            case 'Metadata':
            case 'Difficulty':
            {
                // let [key, ...value] = line.split(':');
                var data = line.split(':'),
                    key = data.shift(),
                    value = data.join(':');
                if (key in this)
                {
                    this[key] = parseFloat(value) == value ? +value : value;
                }
                break;
            }
            case 'TimingPoints':
            {
                try
                {
                    this.TimingPoints.push(new TimingPoint(line));
                }
                catch (e) {}
                break;
            }
            case 'Colours':
            {
                // let [key, value] = line.split(':');
                var data = line.split(':');
                if (/^Combo\d+/.test(data[0]))
                {
                    this.Colors.push('rgb(' + data[1] + ')');
                }
                break;
            }
            case 'HitObjects':
            {
                try
                {
                    this.HitObjects.push(HitObject.parse(line, this));
                }
                catch (e) { console.log(e); }
                break;
            }
        }
    }
    this.HitObjects.sort((a, b) => a.time - b.time);
}
Object.defineProperties(Beatmap.prototype, {
    Version: {
        get: function()
        {
            return typeof this._Version == 'undefined' || /^$/.test(this._Version)
                ? 'Normal'
                : this._Version;
        },
        set: function(value)
        {
            this._Version = value;
        }
    },
    ApproachRate: {
        get: function()
        {
            return typeof this._ApproachRate == 'undefined'
                ? this.OverallDifficulty
                : this._ApproachRate;
        },
        set: function(value)
        {
            this._ApproachRate = value;
        }
    },
    hitObjectTypeMask: {
        get: function()
        {
            if (typeof this._hitObjectTypeMask == 'undefined')
            {
                this._hitObjectTypeMask = Object.keys(this.hitObjectTypes).reduce(function(a, b)
                {
                    return a | b;
                });
            }
            return this._hitObjectTypeMask;
        }
    }
});
Beatmap.prototype.hitObjectTypes = undefined;
Beatmap.prototype.update = undefined;
Beatmap.prototype.draw = undefined;
Beatmap.prototype.processBG = undefined;
Beatmap.WIDTH = 640;
Beatmap.HEIGHT = 480;
Beatmap.MAX_X = 512;
Beatmap.MAX_Y = 384;
Beatmap.modes = {};
Beatmap.parse = function(osu)
{
    if (!/^osu/.test(osu))
    {
        throw 'target is not a beatmap file';
    }

    // default mode is standard(id: 0)
    var mode = +((osu.match(/[\r\n]Mode.*?:(.*?)[\r\n]/) || [])[1]) || 0;
    if (!(mode in Beatmap.modes))
    {
        throw 'we do not support this beatmap mode';
    }

    return new Beatmap.modes[mode](osu);
};
Beatmap.prototype.timingPointIndexAt = function(time)
{
    var begin = 0,
        end = this.TimingPoints.length - 1;
    while (begin <= end)
    {
        var mid = (begin + end) / 2 | 0;
        if (time >= this.TimingPoints[mid].time)
        {
            if (mid + 1 == this.TimingPoints.length ||
                time < this.TimingPoints[mid + 1].time)
            {
                return mid;
            }
            begin = mid + 1;
        }
        else
        {
            end = mid - 1;
        }
    }
    return 0;
};
Beatmap.prototype.timingPointAt = function(time)
{
    return this.TimingPoints[this.timingPointIndexAt(time)];
};
Beatmap.prototype.refresh = function()
{
    this.tmp = {};
};
Beatmap.prototype.toString = function()
{
    var unicode = JSON.parse(localStorage['osu_tool'] || '{"unicode":false}')['unicode'];
    return [
        (unicode ?
            [
                this.ArtistUnicode || this.Artist,
                this.TitleUnicode || this.Title
            ] :
            [
                this.Artist,
                this.Title
            ]
        ).join(' - '),
        ' (', this.Creator, ')',
        ' [', this.Version || 'Normal' , ']'
    ].join('');
};
