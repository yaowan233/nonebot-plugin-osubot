class LegacyRandom{
    constructor(x) {
        this.int_to_real = 1 / 2147483648;
        this.int_mask = 0x7FFFFFFF;
        this.x = x || Date.now();
        this.x = this.ToUInt(this.x);
        this._X = this.x;
        this.y = 842502087;
        this._Y = this.y;
        this.z = 3579807591;
        this._Z = this.z;
        this.w = 273326509;
        this._W = this.w;

        this.bitBuffer;
        this.bitIndex = 32;
    }

    ToInt(num) {
        if (num > 2147483647) return this.ToInt(num - 4294967296);
        else if (num < -2147483648) return this.ToInt(4294967296 + num);
        else return parseInt(num);
    }

    ToUInt(num) {
        if (num > 4294967296) return this.ToUInt(num - 4294967296);
        if (num < 0) return this.ToUInt(4294967296 + num);
        else return num;
    }

    NextUInt() {
        let t = this.ToUInt(this._X ^ this.ToUInt(this._X << 11));
        this._X = this._Y;
        this._Y = this._Z;
        this._Z = this._W;
        let tmp = this.ToUInt(this._W >>> 19);
        tmp = this.ToUInt(this._W ^ tmp);
        tmp = this.ToUInt(tmp ^ t);
        let tmp2 = this.ToUInt(t >>> 8);
        this._W = this.ToUInt(tmp ^ tmp2);
        return this._W;
    }

    Next() {
        if (arguments.length <= 0) {
            return this.ToInt(this.int_mask & this.NextUInt());
        }
        else if (arguments.length === 1) { // upperBound
            return this.ToInt(this.NextDouble() * arguments[0]);
        }
        else { // lowerBound, upperBound
            return this.ToInt(arguments[0] + this.NextDouble() * (arguments[1] - arguments[0]));
        }
    }

    NextDouble() {
        return this.int_to_real * this.Next();
    }

    NextBool() {
        if (this.bitIndex == 32)
        {
            this.bitBuffer = this.NextUInt();
            this.bitIndex = 1;

            return ((this.bitBuffer & 1) == 1);
        }

        this.bitIndex++;
        this.bitBuffer = this.bitBuffer >>> 1;
        return ((this.bitBuffer & 1) == 1);
    }
}
/*
let rng = new LegacyRandom(1337);
for(let i = 0; i < 1000;  i++)
{
    rng.NextDouble();
}
console.log(rng.NextDouble());
*/
