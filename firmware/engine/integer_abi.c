// Only low MUL is implemented by this SoC. Do not enable the whole RISC-V M ISA.
#include <stdint.h>
typedef union {uint64_t u;struct {uint32_t lo,hi;} w;} U64;
uint32_t __mulsi3(uint32_t a,uint32_t b){
#ifdef __riscv
    uint32_t r;__asm__ volatile(".insn r 0x33, 0, 1, %0, %1, %2":"=r"(r):"r"(a),"r"(b));return r;
#else
    return a*b;
#endif
}
uint32_t __udivmodsi4(uint32_t a,uint32_t b,uint32_t *rem){
    uint32_t q=0,r=0;
    if(!b){if(rem)*rem=a;return UINT32_MAX;}
    for(int bit=31;bit>=0;--bit){uint32_t carry=r>>31;r=(r<<1)|((a>>bit)&1u);if(carry||r>=b){r-=b;q|=1u<<bit;}}
    if(rem)*rem=r;return q;
}
uint32_t __udivsi3(uint32_t a,uint32_t b){return __udivmodsi4(a,b,0);}
uint32_t __umodsi3(uint32_t a,uint32_t b){uint32_t r;__udivmodsi4(a,b,&r);return r;}
int32_t __divsi3(int32_t a,int32_t b){uint32_t x=a<0?0u-(uint32_t)a:(uint32_t)a,y=b<0?0u-(uint32_t)b:(uint32_t)b;uint32_t q=__udivsi3(x,y);return (int32_t)((a<0)!=(b<0)?0u-q:q);}
int32_t __modsi3(int32_t a,int32_t b){uint32_t x=a<0?0u-(uint32_t)a:(uint32_t)a,y=b<0?0u-(uint32_t)b:(uint32_t)b;uint32_t r=__umodsi3(x,y);return (int32_t)(a<0?0u-r:r);}
uint64_t __ashldi3(uint64_t a,int n){U64 x={.u=a},r={0};n&=63;if(!n)return a;if(n<32){r.w.hi=(x.w.hi<<n)|(x.w.lo>>(32-n));r.w.lo=x.w.lo<<n;}else r.w.hi=x.w.lo<<(n-32);return r.u;}
uint64_t __lshrdi3(uint64_t a,int n){U64 x={.u=a},r={0};n&=63;if(!n)return a;if(n<32){r.w.lo=(x.w.lo>>n)|(x.w.hi<<(32-n));r.w.hi=x.w.hi>>n;}else r.w.lo=x.w.hi>>(n-32);return r.u;}
int64_t __ashrdi3(int64_t a,int n){U64 x={.u=(uint64_t)a},r;n&=63;if(!n)return a;r.w.hi=(uint32_t)((int32_t)x.w.hi>>(n<32?n:31));r.w.lo=n<32?(x.w.lo>>n)|(x.w.hi<<(32-n)):(uint32_t)((int32_t)x.w.hi>>(n-32));return (int64_t)r.u;}
uint64_t __muldi3(uint64_t a,uint64_t b){U64 x={.u=a},y={.u=b},r;uint32_t a0=x.w.lo&65535u,a1=x.w.lo>>16,b0=y.w.lo&65535u,b1=y.w.lo>>16;
    uint32_t p0=__mulsi3(a0,b0),p1=__mulsi3(a0,b1),p2=__mulsi3(a1,b0),p3=__mulsi3(a1,b1);
    uint32_t mid=(p0>>16)+(p1&65535u)+(p2&65535u);r.w.lo=(p0&65535u)|(mid<<16);
    r.w.hi=p3+(p1>>16)+(p2>>16)+(mid>>16)+__mulsi3(x.w.lo,y.w.hi)+__mulsi3(x.w.hi,y.w.lo);return r.u;
}
int __clzsi2(uint32_t a){int n=0;if(!a)return 32;while(!(a&0x80000000u)){a<<=1;++n;}return n;}
int __clzdi2(uint64_t a){U64 x={.u=a};return x.w.hi?__clzsi2(x.w.hi):32+__clzsi2(x.w.lo);}
int abs(int x){return x<0?-x:x;}
