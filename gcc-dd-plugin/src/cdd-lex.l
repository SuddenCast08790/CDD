/* C Decrease Decrease (.cdd) lexer -- flex scanner for the g--cc driver.
   Chopped from plain C: no semicolons, no braces, no for, no ==. */
%{
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef enum {
    TK_EOF_, TK_ID, TK_NUM, TK_STR,
    /* keywords */
    TK_IS, TK_ISNT, TK_ALSO, TK_ELSEAND, TK_LOOP, TK_FROM, TK_TO, TK_UNTIL,
    TK_BACK, TK_SKIP, TK_HALT, TK_BORROW, TK_SHOUT, TK_WHISPER, TK_IF, TK_UNLESS,
    TK_OTHERWISE, TK_PICK, TK_CASE, TK_THUNK, TK_MAYBE, TK_NOTHING, TK_NEW,
    TK_TRUE_, TK_FALSE_, TK_GOTO, TK_FUNC,
    /* punctuation */
    TK_COLON, TK_NL, TK_LPAREN, TK_RPAREN, TK_LBRACK, TK_RBRACK,
    TK_CARET, TK_PLUSPLUS, TK_MINUSMINUS, TK_PLUS, TK_MINUS, TK_STAR, TK_SLASH,
    TK_PERCENT, TK_ASSIGN, TK_LT, TK_GT, TK_LE, TK_GE, TK_COMMA, TK_DOT,
} toktype;

#define MAXTOKS 200000
typedef struct { toktype t; char *text; long numval; int line; } Tok;
Tok toks[MAXTOKS];
int ntoks = 0;
int cur_line = 1;

static void emit(toktype t) {
    if (ntoks >= MAXTOKS) { fprintf(stderr, "g--cc: too many tokens; the axe stopped you\n"); exit(1); }
    toks[ntoks].t = t; toks[ntoks].text = NULL; toks[ntoks].numval = 0; toks[ntoks].line = cur_line;
    ntoks++;
}
static void emit_text(toktype t, const char *s) {
    emit(t); toks[ntoks-1].text = strdup(s);
}

void yyerror(const char *fmt, ...);

%}
%option noyywrap nounput noinput
WS      [ \t\r]+
ID      [A-Za-z_][A-Za-z0-9_]*
NUM     [0-9]+

%%
{WS}                { return 1; }
"#[^\n]*"           { cur_line++; return 1; }   /* comment eats its own line */
\{\{[^}]*\}\}       { yyerror("C Decrease Decrease: double braces are contraband; the axe found them at line %d", cur_line); exit(1); }
"\n"                { cur_line++; if (ntoks>0 && toks[ntoks-1].t!=TK_NL && toks[ntoks-1].t!=TK_COLON &&
                        toks[ntoks-1].t!=TK_COMMA && toks[ntoks-1].t!=TK_LPAREN && toks[ntoks-1].t!=TK_LBRACK &&
                        toks[ntoks-1].t!=TK_IS && toks[ntoks-1].t!=TK_ISNT && toks[ntoks-1].t!=TK_FROM &&
                        toks[ntoks-1].t!=TK_TO && toks[ntoks-1].t!=TK_ALSO && toks[ntoks-1].t!=TK_ELSEAND &&
                        toks[ntoks-1].t!=TK_ASSIGN && toks[ntoks-1].t!=TK_PLUS && toks[ntoks-1].t!=TK_MINUS &&
                        toks[ntoks-1].t!=TK_STAR && toks[ntoks-1].t!=TK_SLASH && toks[ntoks-1].t!=TK_PERCENT &&
                        toks[ntoks-1].t!=TK_LT && toks[ntoks-1].t!=TK_GT && toks[ntoks-1].t!=TK_LE &&
                        toks[ntoks-1].t!=TK_GE && toks[ntoks-1].t!=TK_MAYBE)
                        emit(TK_NL);
                    return 1; } 
"is"                emit(TK_IS); return 1;
"isnt"              emit(TK_ISNT); return 1;
"&also"             emit(TK_ALSO); return 1;
"|else&"            emit(TK_ELSEAND); return 1;
"loop"              emit(TK_LOOP); return 1;
"from"              emit(TK_FROM); return 1;
"to"                emit(TK_TO); return 1;
"until"             emit(TK_UNTIL); return 1;
"back"              emit(TK_BACK); return 1;
"skip"              emit(TK_SKIP); return 1;
"halt"              emit(TK_HALT); return 1;
"borrow"            emit(TK_BORROW); return 1;
"shout"             emit(TK_SHOUT); return 1;
"whisper"           emit(TK_WHISPER); return 1;
"if"                emit(TK_IF); return 1;
"unless"            emit(TK_UNLESS); return 1;
"otherwise"         emit(TK_OTHERWISE); return 1;
"pick"              emit(TK_PICK); return 1;
"case"              emit(TK_CASE); return 1;
"thunk"             emit(TK_THUNK); return 1;
"maybe"             emit(TK_MAYBE);
"nothing"           emit(TK_NOTHING); return 1;
"new"               emit(TK_NEW); return 1;
"true"              emit(TK_TRUE_); return 1;
"false"             emit(TK_FALSE_); return 1;
"goto"              { yyerror("C Decrease Decrease: 'goto' was chopped off in v-1; use loop/until (line %d)", cur_line); exit(1); }
"for"|"while"|"do"  { yyerror("C Decrease Decrease: '%s' is dead; long live 'loop ... until' (line %d)", yytext, cur_line); exit(1); }
"return"            { yyerror("C Decrease Decrease: 'return' died with the semicolon; last expression backs out (line %d)", cur_line); exit(1); }
"=="|"!="           { yyerror("C Decrease Decrease: '%s' forbidden; say 'is' / 'isnt' (line %d)", yytext, cur_line); exit(1); }
";"                 { yyerror("C Decrease Decrease: semicolon detected at line %d. Semicolons are illegal. The newline already did its job.", cur_line); exit(1); }
":"                 emit(TK_COLON); return 1;
"("                emit(TK_LPAREN); return 1;
")"                 emit(TK_RPAREN); return 1;
"["                 emit(TK_LBRACK); return 1;
"]"                 emit(TK_RBRACK); return 1;
"^"                 emit(TK_CARET); return 1;
"++"                emit(TK_PLUSPLUS); return 1;
"--"                emit(TK_MINUSMINUS); return 1;
"+"                 emit(TK_PLUS); return 1;
"-"                 emit(TK_MINUS); return 1;
"*"                 emit(TK_STAR); return 1;
"/"                 emit(TK_SLASH); return 1;
"%"                 emit(TK_PERCENT); return 1;
"="                 emit(TK_ASSIGN); return 1;
"<="                emit(TK_LE); return 1;
">="                emit(TK_GE); return 1;
"<"                 emit(TK_LT); return 1;
">"                 emit(TK_GT); return 1;
","                 emit(TK_COMMA); return 1;
"."                 emit(TK_DOT); return 1;
{NUM}               { emit(TK_NUM); toks[ntoks-1].numval = atol(yytext); return 1; }
{ID}                emit_text(TK_ID, yytext); return 1;
\"                  { /* string: capture raw, interpolations handled by codegen */
                      static char buf[4096]; int i=0; int c;
                      while ((c = fgetc(yyin)) != EOF && c != '"') { if (i < 4095) buf[i++] = (char)c; }
                      if (c == EOF) { yyerror("unterminated string (line %d)", cur_line); exit(1); }
                      buf[i] = 0; emit_text(TK_STR, buf); return 1; }
.                   { yyerror("C Decrease Decrease: stray character '%s' (line %d) — the axe missed it", yytext, cur_line); exit(1); }
<<EOF>>             { emit(TK_EOF_); return 0; }
%%
