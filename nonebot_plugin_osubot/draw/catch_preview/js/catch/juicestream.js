function JuiceStream(data, beatmap)
{
    Slider.call(this, data, beatmap);

    this.points = data[5].split('|');
    this.sliderType = this.points[0];
    this.points[0] = this.position;
    for (var i = 1; i < this.points.length; i++)
    {
        this.points[i] = new Point(this.points[i].split(':'));
    }
    this.repeat = data[6] | 0;
    this.pixelLength = +data[7];

    this.timingPoint = this.beatmap.timingPointAt(this.time);
    this.beatLength = this.timingPoint.beatLength;
    this.timingPointStart = this.timingPoint.time;

    this.sliderTime = this.beatLength * ( this.pixelLength / this.beatmap.SliderMultiplier ) / 100;
    this.velocityFactor = 100 * this.beatmap.SliderMultiplier / this.beatLength;
    this.tickDistanceFactor = 100 * this.beatmap.SliderMultiplier / this.beatmap.SliderTickRate;
    this.velocity = this.velocityFactor * this.timingPoint.sliderVelocity;
    this.tickDistance = this.tickDistanceFactor * this.timingPoint.sliderVelocity;

    this.endTime = this.time + this.sliderTime * this.repeat;
    this.duration = this.endTime - this.time;

    this.spanCount = parseInt(this.repeat);

    this.curve = Curve.parse(this.sliderType, this.points, this.pixelLength);

    this.endPosition = this.curve.pointAt(1);

    this.max_length = 100000;
    let length = Math.min(this.max_length, this.pixelLength);
    this.tickDistance = Math.clamp(this.tickDistance, 0, length);
    this.minDistanceFromEnd = this.velocity * 10;

    this.events = [];
    this.events.push({type: "head", time: this.time, pathProgress: 0});
    if (this.tickDistance != 0) {
        for (let span = 0; span < this.spanCount; span++) {
            let spanStartTime = this.time + span * this.sliderTime;
            let reversed = span % 2 == 1;
            let ticks = this.generateTicks(span, spanStartTime, this.sliderTime, reversed, length, this.tickDistance, this.minDistanceFromEnd);
            if (reversed) ticks = ticks.reverse();
            this.events.push(...ticks);
            if (span < this.spanCount - 1)
            {
                this.events.push({
                    type: "repeat", 
                    time: spanStartTime + this.sliderTime,
                    pathProgress: (span + 1) % 2
                });
            }
        }
    }

    let legacyLastTickOffset = 36;
    let finalSpanIndex = this.spanCount - 1;
    let finalSpanStartTime = this.time + finalSpanIndex * this.sliderTime;
    let finalSpanEndTime = Math.max(this.time + this.duration / 2, (finalSpanStartTime + this.sliderTime) - legacyLastTickOffset);
    let finalProgress = (finalSpanEndTime - finalSpanStartTime) / this.sliderTime;

    if (this.spanCount % 2 == 0) finalProgress = 1 - finalProgress;

    this.events.push({
        type: "legacyLastTick", 
        time: finalSpanEndTime,
        pathProgress: finalProgress
    });

    this.events.push({
        type: "tail", 
        time: this.endTime,
        pathProgress: this.spanCount % 2
    });

    this.nested = [];
}
JuiceStream.prototype = Object.create(Slider.prototype);
JuiceStream.prototype.constructor = JuiceStream;
JuiceStream.ID = 2;
Catch.prototype.hitObjectTypes[JuiceStream.ID] = JuiceStream;
JuiceStream.prototype.generateTicks = function(spanIndex, spanStartTime, spanDuration, reversed, length, tickDistance, minDistanceFromEnd) {
    let ticks = [];
    for (let d = tickDistance; d <= length; d += tickDistance) {
        if (d >= length - minDistanceFromEnd)
        break;

        let pathProgress = d / length;
        let timeProgress = reversed ? 1 - pathProgress : pathProgress;

        ticks.push({type: "tick", time: spanStartTime + timeProgress * spanDuration, pathProgress});
    }
    return ticks;
}

JuiceStream.prototype.buildNested = function() {
    this.nested = [];

    let lastEvent = null;
    for(let i = 0; i < this.events.length; i++) {
        // generate tiny droplets since the last point
        if (lastEvent != null)
        {
            let sinceLastTick = this.events[i].time - lastEvent.time;
            if (sinceLastTick > 80)
            {
                let timeBetweenTiny = sinceLastTick;
                while (timeBetweenTiny > 100) timeBetweenTiny /= 2;
                for (let t = timeBetweenTiny; t < sinceLastTick; t += timeBetweenTiny) {
                    let repeat = (t + lastEvent.time - this.time) * this.repeat / this.duration;
                    repeat %= 2;
                    if (repeat > 1) repeat = 2 - repeat;
                    var point = this.curve.pointAt(repeat);
                    this.nested.push(new PalpableCatchHitObject({
                        type: "TinyDroplet",
                        time: t + lastEvent.time,
                        x: point.x,
                        // x: this.curve.pointAt(lastEvent.pathProgress + (t / sinceLastTick) * (this.events[i].pathProgress - lastEvent.pathProgress)).x,
                        color: this.color,
                        radius: this.beatmap.tinyRadius,
                    }, this.beatmap));
                }
            }
        }

        // this also includes LegacyLastTick and this is used for TinyDroplet generation above.
        // this means that the final segment of TinyDroplets are increasingly mistimed where LegacyLastTickOffset is being applied.
        lastEvent = this.events[i];

        switch (this.events[i].type)
        {
            case "tick":
                this.nested.push(new PalpableCatchHitObject({
                    type: "Droplet",
                    time: this.events[i].time,
                    x: this.curve.pointAt(this.events[i].pathProgress).x,
                    color: this.color,
                    radius: this.beatmap.smallRadius,
                }, this.beatmap));
                break;

            case "head":
            case "tail":
            case "repeat":
                this.nested.push(new PalpableCatchHitObject({
                    type: "Fruit",
                    time: this.events[i].time,
                    x: this.curve.pointAt(this.events[i].pathProgress).x,
                    color: this.color,
                    radius: this.beatmap.circleRadius,
                }, this.beatmap));
                break;
        }
    }

    /* TODO BUG!!!
     * 在预览 #4057684 时第一个滑条出现了
     * PalpableCatchHitObject {beatmap: Catch, type: 'TinyDroplet', time: 464.57142857142895, …}
     * PalpableCatchHitObject {beatmap: Catch, type: 'Droplet', time: 464.571428571429, …}
     * 物件数量偏差导致后续随机数错误
     * 暂时找不到原因，可能因为计算精度问题，临时手动将其剔除
     */
    let tmp_droplets = this.nested.filter((item) => item.type === "Droplet");
    this.nested = this.nested.filter((item) => {
        if (item.type != "TinyDroplet") return true;
        for (let td = 0; td < tmp_droplets.length; td++) {
            if (Math.abs(item.time - tmp_droplets[td].time) < 0.01) {
                console.warn("丢弃重复TinyDroplet，可能引起谱面错误", item);
                return false;
            }
        }
        return true;
    });

    return this;
}
