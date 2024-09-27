function HitObject(data, beatmap)
{
    this.beatmap = beatmap;

    this.position = new Point(data);
    this.endPosition = this.position.clone();
    this.time = data[2] | 0;
    this.endTime = this.time;
    this.flag = data[3] | 0;
    this.hitSound = data[4] | 0;
}
HitObject.prototype.draw = undefined;
HitObject.parse = function(line, beatmap)
{
    var data = line.split(',');
    if (data.length < 5)
    {
        throw 'invalid data: ' + line;
    }

    var type = data[3] & beatmap.hitObjectTypeMask;
    if (!(type in beatmap.hitObjectTypes))
    {
        // throw 'we do not support this hitobject type';
        return new HitObject(data, beatmap);
    }

    return new beatmap.hitObjectTypes[type](data, beatmap);
};
