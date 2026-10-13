// Compiler ABI boundary. Original engine float/double expressions stay intact.
#include <stdint.h>
#include "softfloat.h"
typedef union {float f;uint32_t u;} F32;
typedef union {double f;uint64_t u;} F64;
static float32_t sf(float x){F32 a={.f=x};return (float32_t){a.u};}
static float ff(float32_t x){F32 a={.u=x.v};return a.f;}
static float64_t sd(double x){F64 a={.f=x};return (float64_t){a.u};}
static double dd(float64_t x){F64 a={.u=x.v};return a.f;}
float __addsf3(float a,float b){return ff(f32_add(sf(a),sf(b)));}
float __subsf3(float a,float b){return ff(f32_sub(sf(a),sf(b)));}
float __mulsf3(float a,float b){return ff(f32_mul(sf(a),sf(b)));}
float __divsf3(float a,float b){return ff(f32_div(sf(a),sf(b)));}
float __negsf2(float a){F32 x={.f=a};x.u^=0x80000000u;return x.f;}
float __floatsisf(int32_t a){return ff(i32_to_f32(a));}
float __floatunsisf(uint32_t a){return ff(ui32_to_f32(a));}
int32_t __fixsfsi(float a){return (int32_t)f32_to_i32_r_minMag(sf(a),false);}
uint32_t __fixunssfsi(float a){return (uint32_t)f32_to_ui32_r_minMag(sf(a),false);}
int __unordsf2(float a,float b){F32 x={.f=a},y={.f=b};return (x.u&0x7fffffffu)>0x7f800000u||(y.u&0x7fffffffu)>0x7f800000u;}
int __lesf2(float a,float b){if(__unordsf2(a,b))return 1;if(f32_eq(sf(a),sf(b)))return 0;return f32_lt(sf(a),sf(b))?-1:1;}
int __gesf2(float a,float b){if(__unordsf2(a,b))return -1;return __lesf2(a,b);}
int __eqsf2(float a,float b){return __lesf2(a,b);}
int __nesf2(float a,float b){return __lesf2(a,b);}
int __ltsf2(float a,float b){return __lesf2(a,b);}
int __gtsf2(float a,float b){return __gesf2(a,b);}
float sqrtf(float a){return ff(f32_sqrt(sf(a)));}
float fabsf(float a){F32 x={.f=a};x.u&=0x7fffffffu;return x.f;}
double sqrt(double a){return dd(f64_sqrt(sd(a)));}
double __extendsfdf2(float a){return dd(f32_to_f64(sf(a)));}
float __truncdfsf2(double a){return ff(f64_to_f32(sd(a)));}
double __adddf3(double a,double b){return dd(f64_add(sd(a),sd(b)));}
double __subdf3(double a,double b){return dd(f64_sub(sd(a),sd(b)));}
double __muldf3(double a,double b){return dd(f64_mul(sd(a),sd(b)));}
double __divdf3(double a,double b){return dd(f64_div(sd(a),sd(b)));}
double __floatsidf(int32_t a){return dd(i32_to_f64(a));}
double __floatunsidf(uint32_t a){return dd(ui32_to_f64(a));}
int32_t __fixdfsi(double a){return (int32_t)f64_to_i32_r_minMag(sd(a),false);}
uint32_t __fixunsdfsi(double a){return (uint32_t)f64_to_ui32_r_minMag(sd(a),false);}
int __unorddf2(double a,double b){F64 x={.f=a},y={.f=b};return (x.u&UINT64_C(0x7fffffffffffffff))>UINT64_C(0x7ff0000000000000)||(y.u&UINT64_C(0x7fffffffffffffff))>UINT64_C(0x7ff0000000000000);}
int __ledf2(double a,double b){if(__unorddf2(a,b))return 1;if(f64_eq(sd(a),sd(b)))return 0;return f64_lt(sd(a),sd(b))?-1:1;}
int __gedf2(double a,double b){if(__unorddf2(a,b))return -1;return __ledf2(a,b);}
int __eqdf2(double a,double b){return __ledf2(a,b);}
int __nedf2(double a,double b){return __ledf2(a,b);}
int __ltdf2(double a,double b){return __ledf2(a,b);}
int __gtdf2(double a,double b){return __gedf2(a,b);}
