/* C Decrease Decrease: parser + code generator (token stream -> lowered C).
   Single-pass recursive descent over the flex token array; emits GNU-C text
   (statement-expressions allowed) which the g--cc driver feeds to cc1. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

typedef enum {
    TK_EOF_, TK_ID, TK_NUM, TK_STR,
    TK_IS, TK_ISNT, TK_ALSO, TK_ELSEAND, TK_LOOP, TK_FROM, TK_TO, TK_UNTIL,
    TK_BACK, TK_SKIP, TK_HALT, TK_BORROW, TK_SHOUT, TK_WHISPER, TK_IF, TK_UNLESS,
    TK_OTHERWISE, TK_PICK, TK_CASE, TK_THUNK, TK_MAYBE, TK_NOTHING, TK_NEW,
    TK_TRUE_, TK_FALSE_, TK_GOTO, TK_FUNC,
    TK_COLON, TK_NL, TK_LPAREN, TK_RPAREN, TK_LBRACK, TK_RBRACK,
    TK_CARET, TK_PLUSPLUS, TK_MINUSMINUS, TK_PLUS, TK_MINUS, TK_STAR, TK_SLASH,
    TK_PERCENT, TK_ASSIGN, TK_LT, TK_GT, TK_LE, TK_GE, TK_COMMA, TK_DOT,
} toktype;
typedef struct { toktype t; char *text; long numval; int line; } Tok;
extern Tok toks[]; extern int ntoks;

static int pos = 0;
#define CUR (toks[pos].t)
#define CTX (toks[pos].text)
static void adv(void){ if(pos<ntoks-1) pos++; }
static void expect(toktype t,const char*w){
    if(CUR!=t){ fprintf(stderr,"g--cc parse error line %d: expected %s\n",toks[pos].line,w); exit(1);} adv(); }
static int at(toktype t){ return CUR==t; }
static int peek_is(int k,toktype t){ return (pos+k<ntoks)&&toks[pos+k].t==t; }

/* ---------- output buffer ---------- */
static char out[1<<22]; static size_t olen=0;
static void P(const char*s){ while(*s&&olen<sizeof(out)-1) out[olen++]=*s++; }
static void Pf(const char*f,...){ va_list a;va_start(a,f);
    olen+=vsnprintf(out+olen,sizeof(out)-olen,f,a); va_end(a);
    if(olen>=sizeof(out)-1)olen=sizeof(out)-1; }

/* ---------- expression sub-parser on a saved token slice ---------- */
/* For interpolations "{expr}" we re-scan a small token window by saving
   the whole toks array region — simpler: interpolation exprs are parsed
   inline during shout lowering using a nested cursor. We implement it via
   setjmp-free approach: shout stores raw string; at emit time we split it
   and recursively call cdd_expr_on() over a temp token copy. */
static void expr(void);          /* forward: parses at global pos */
static void stmt(void);

static int tmpc=0;
static char* newtmp(void){ static char b[512][16]; int i=tmpc%512; sprintf(b[i],"_t%d",tmpc++); return b[i]; }

/* ---------- blocks ---------- */
static int stop_body(void){ return at(TK_EOF_)||at(TK_OTHERWISE)||at(TK_CASE)||at(TK_RPAREN); }
static void body(void){ /* starts at ':' */
    expect(TK_COLON,": to open a block");
    if(at(TK_NL)) adv();
    P("{ ");
    while(!stop_body()){
        if(at(TK_NL)){adv();continue;}
        if(at(TK_UNTIL)) break;   /* loop tail: caller handles 'until' */
        stmt(); P(" ;");
        while(at(TK_NL)) adv();
    }
    P(" }");
}
static void single(void){ /* ': block' or one statement */
    if(at(TK_COLON)) body();
    else { P("{ "); stmt(); P(" ; }"); }
}
/* after a loop body, consume optional 'until cond' and splice break into it */
static void loop_until_tail(void){
    while(at(TK_NL)) adv();
    if(at(TK_UNTIL)){
        adv();
        P(" if ("); expr(); P(") break;");
    }
}

/* ---------- expressions ---------- */
static const char* binop(void){ switch(CUR){
 case TK_PLUS:return"+";case TK_MINUS:return"-";case TK_STAR:return"*";case TK_SLASH:return"/";
 case TK_PERCENT:return"%";case TK_LT:return"<";case TK_GT:return">";case TK_LE:return"<=";case TK_GE:return">=";
 default:return 0; } }

static void primary(void){
    switch(CUR){
    case TK_NUM: Pf("%ld",toks[pos].numval); adv(); break;
    case TK_ID: {
        char *id=CTX; adv();
        if(at(TK_CARET)){ adv(); Pf("(*( %s ))",id); }              /* p^ deref rvalue */
        else if(at(TK_LPAREN)){ P(id); P("("); adv();
            if(!at(TK_RPAREN)){ expr(); while(at(TK_COMMA)){adv();expr();} }
            expect(TK_RPAREN,")"); P(")"); }
        else if(at(TK_LBRACK)){ P(id); P("["); adv(); expr(); expect(TK_RBRACK,"]"); P("]"); }
        else P(id);
        break; }
    case TK_LPAREN: P("("); adv(); expr(); while(at(TK_COMMA)){adv();expr();} expect(TK_RPAREN,")"); P(")"); break;
    case TK_STR: P("\""); for(char*q=CTX;*q;q++){ if(*q=='"')P("\\\""); else if(*q=='\\')P("\\\\"); else {char c[2]={*q,0};P(c);} } P("\""); adv(); break;
    case TK_TRUE_: P("1"); adv(); break;
    case TK_FALSE_: P("0"); adv(); break;
    case TK_NOTHING: P("0"); adv(); break;
    case TK_MAYBE: { /* maybe(a,b,c): first non-zero */
        adv(); expect(TK_LPAREN,"( after maybe");
        P("({ long _m; ");
        Pf("_m = ("); expr(); Pf(") );\n");
        while(at(TK_COMMA)){ adv(); Pf("if(_m==0){ _m = ("); expr(); Pf("); } "); }
        expect(TK_RPAREN,") to close maybe");
        Pf("_m })");
        break; }
    case TK_MINUS: P("( -"); adv(); expr(); P(" )"); break;
    case TK_PLUS: adv(); expr(); break;
    default: fprintf(stderr,"g--cc parse error line %d: unexpected token in expression\n",toks[pos].line); exit(1); }
}
static void mul_expr(void){ primary(); while(at(TK_STAR)||at(TK_SLASH)||at(TK_PERCENT)){ Pf(" %s ",binop()); adv(); primary(); } }
static void add_expr(void){ mul_expr(); while(at(TK_PLUS)||at(TK_MINUS)){ Pf(" %s ",at(TK_PLUS)?"+":"-"); adv(); mul_expr(); } }
static void rel_expr(void){ add_expr(); while(at(TK_LT)||at(TK_GT)||at(TK_LE)||at(TK_GE)){ Pf(" %s ",binop()); adv(); add_expr(); } }
static void eq_expr(void){ rel_expr(); while(at(TK_IS)||at(TK_ISNT)){ Pf(" %s ",at(TK_IS)?"==":"!="); adv(); rel_expr(); } }
static void and_expr(void){ eq_expr(); while(at(TK_ALSO)){ P(" && "); adv(); eq_expr(); } }
static void or_expr(void){ and_expr(); while(at(TK_ELSEAND)){ P(" || "); adv(); and_expr(); } }
static void expr(void){ or_expr(); }

/* ---------- shout/whisper with {interp} ---------- */
/* We lower shout("a{x}b") into printf pieces. Interpolated subexpressions
   are parsed by temporarily splicing their tokens: easiest correct route is
   to pre-tokenize the interp text with the same lexer rules — but since the
   lexer already ran over the whole file, interp content lives inside a
   TK_STR blob. So we hand-parse simple cases: identifiers, numbers, and
   ident^ / ident(args) forms, enough for the language's promise. */
static void emit_interp_args(const char *s, int nl)
{
    char fmt[8192]; size_t fi=0; int narg=0;
    P("printf(\"");
    /* build format & arg list in one pass: write args first into a side buffer */
    char argbuf[8192]; size_t ai=0;
    const char *q=s;
    while(*q){
        if(*q=='{' ){
            const char*e=strchr(q,'}');
            if(!e){ if(fi<8000) fmt[fi++]=*q++; continue; }
            /* parse the little expression between q+1..e-1 manually */
            char sub[512]; size_t sl=(size_t)(e-q-1); if(sl>=sizeof(sub))sl=sizeof(sub)-1;
            memcpy(sub,q+1,sl); sub[sl]=0;
            /* we always use %ld for numeric interps; strings unsupported yet */
            fi += snprintf(fmt+fi,sizeof(fmt)-fi,"%%ld");
            ai += snprintf(argbuf+ai,sizeof(argbuf)-ai,", (long)(%s)",sub);
            narg++; q=e+1;
        } else {
            if(*q=='%'&&fi<8000) fmt[fi++]='%';
            if(fi<8000) fmt[fi++]=*q++;
        }
    }
    if(nl){ fmt[fi++]='\\'; fmt[fi++]='n'; }
    fmt[fi]=0;
    P(fmt); P("\""); P(argbuf); P(")");
}
static void shout_stmt(int nl){
    adv(); /* eat shout/whisper */
    if(at(TK_STR)){ char *s=CTX; adv(); emit_interp_args(s,nl); return; }
    /* shout(expr) form: print as long */
    expect(TK_LPAREN,"string or ( after shout");
    P("printf(\"%ld\\n\""); P(", ");
    expr(); expect(TK_RPAREN,")"); P(")");
}

/* ---------- statements ---------- */
static void stmt(void){
    switch(CUR){
    case TK_BORROW: { adv(); /* borrow <name> : record include */
        /* lexer turned <name> into LT ID GT usually; accept that */
        if(at(TK_LT)){ adv(); char*n=CTX; adv(); expect(TK_GT,">"); Pf("#include <%s>\n",n); }
        else if(at(TK_STR)){ Pf("#include \"%s\"\n",CTX); adv(); }
        else { fprintf(stderr,"g--cc: borrow wants <name> (line %d)\n",toks[pos].line); exit(1);} 
        return; }
    case TK_SHOUT: shout_stmt(1); return;
    case TK_WHISPER: shout_stmt(0); return;
    case TK_IF: { adv(); P("if ("); expr(); P(") "); single();
        while(at(TK_NL)) adv();
        if(at(TK_OTHERWISE)){ adv(); P(" else ");
            if(at(TK_IF)){ /* otherwise if */ adv(); P("if ("); expr(); P(") "); single(); }
            else single(); }
        return; }
    case TK_UNLESS: { adv(); P("if (!("); expr(); P(")) "); single(); return; }
    case TK_LOOP: { adv(); /* loop i from a to b : body until cond | loop : body until cond */
        char *var=0; long a=0,b=0; int ranged=0;
        if(at(TK_ID)){ var=CTX; adv(); expect(TK_FROM,"from");
            a=toks[pos].numval; expect(TK_NUM,"number");
            if(at(TK_TO)){ adv(); b=toks[pos].numval; expect(TK_NUM,"number"); ranged=1; } }
        P("for (");
        if(ranged) Pf("long %s = %ld; %s <= %ld; %s++ ) ",var,a,var,b,var);
        else P("; 1 ; ) ");
        single();
        loop_until_tail();
        return; }
    case TK_PICK: { adv(); P("do { long _pk; ");
        /* pick(x): case v: ... thunk / otherwise */
        expect(TK_LPAREN,"( after pick");
        /* store subject in temp via statement-expr trick */
        P("_pk = ({ "); expr(); P(" });");
        expect(TK_RPAREN,") after pick subject");
        expect(TK_COLON,": after pick(...)");
        if(at(TK_NL)) adv();
        P(" switch(_pk) { ");
        while(at(TK_CASE)||at(TK_OTHERWISE)){
            if(at(TK_CASE)){ adv(); P("case "); expr(); P(" : ");
                /* body until 'thunk' */
                while(!at(TK_THUNK)&&!at(TK_CASE)&&!at(TK_OTHERWISE)&&!at(TK_RPAREN)&&!at(TK_EOF_)){
                    if(at(TK_NL)){adv();continue;} stmt(); P(" ;"); }
                expect(TK_THUNK,"thunk to end case"); P(" break;"); }
            else { adv(); P("default : ");
                while(!at(TK_THUNK)&&!at(TK_CASE)&&!at(TK_RPAREN)&&!at(TK_EOF_)){
                    if(at(TK_NL)){adv();continue;} stmt(); P(" ;"); }
                if(at(TK_THUNK)){ adv(); }
                P(" break;"); }
            while(at(TK_NL)) adv();
        }
        P(" } } while(0)");
        return; }
    case TK_BACK: { adv(); P("return");
        if(!at(TK_NL)&&!at(TK_EOF_)&&!at(TK_RPAREN)&&!at(TK_OTHERWISE)&&!at(TK_CASE)){ P(" "); expr(); }
        return; }
    case TK_SKIP: adv(); P("continue"); return;
    case TK_HALT: adv(); P("exit(0)"); return;
    case TK_NEW: { adv(); /* new num | new ptr | new func name(...) */
        if(at(TK_ID)&&strcmp(CTX,"func")==0){ /* handled at top level */ }
        fprintf(stderr,"g--cc: 'new' was chopped in v-4 (line %d)\n",toks[pos].line); exit(1); return; }
    default: {
        /* assignment: ID = expr | ID^ = expr | ID++ | bare expression */
        if(at(TK_ID)){
            char *id=CTX;
            if(peek_is(1,TK_ASSIGN)){ adv();adv(); Pf("%s = ",id); expr(); return; }
            if(peek_is(1,TK_CARET)&&peek_is(2,TK_ASSIGN)){ adv();adv();adv(); Pf("(* %s) = ",id); expr(); return; }
            if(peek_is(1,TK_PLUSPLUS)){ adv();adv(); Pf("%s ++",id); return; }
            if(peek_is(1,TK_MINUSMINUS)){ adv();adv(); Pf("%s --",id); return; }
        }
        expr(); return; }
    }
}

/* ---------- function definitions ---------- */
/* grammar: name(params) : body   OR   back name(params) : body
   params: comma-separated ids, all long */
static void parse_top(void){
    while(!at(TK_EOF_)){
        while(at(TK_NL)) adv();
        if(at(TK_EOF_)) break;
        if(at(TK_BORROW)){ stmt(); P("\n"); while(at(TK_NL)) adv(); continue; }
        if(!at(TK_ID)){ fprintf(stderr,"g--cc parse error line %d: expected a definition\n",toks[pos].line); exit(1); }
        char *name=CTX; adv();
        int is_func = at(TK_LPAREN);
        if(!is_func){ fprintf(stderr,"g--cc parse error line %d: only functions exist now\n",toks[pos].line); exit(1); }
        P("long "); P(name); P("(");
        adv(); /* ( */
        int first=1;
        while(!at(TK_RPAREN)){
            if(first) first=0; else P(", ");
            Pf("long ");
            if(at(TK_ID)){ P(CTX); adv(); }
            else { expect(TK_ID,"parameter name"); }
            if(at(TK_COMMA)) adv();
        }
        expect(TK_RPAREN,") after parameters");
        body();
        P("\n");
    }
}

int cdd_translate(FILE *fo)
{
    parse_top();
    fputs(out,fo);
    return 0;
}
