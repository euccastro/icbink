($define! $test
  ($vau (name expected . body) env
    (println "Testing" name "...")
    ($let ((result (eval (cons $sequence body) env)))
      ($if (equal? result expected)
        #inert
        (test-error name
                    "; expected:" expected
                    ", actual:" result)))))

; XXX: use a keyed variable when we have those.
($define! current-trace ())

($define! test-env (get-current-environment))

($define! get-trace
  ($lambda () (reverse current-trace)))

($define! reset-trace!
  ($lambda () ($set! test-env current-trace ())))

($define! trace
  ($lambda (x) ($set! test-env current-trace (cons x current-trace))))

($define! $trace-and-result
  ($vau (body . envoper) env
    (reset-trace!)
    ($let ((result (eval (cons $sequence body) ($if (null? envoper) env (car envoper)))))
      (list (get-trace) result))))

; Test with trace.
($define! $t/t
  ($vau (name expected-trace expected-result . body) env
    (println "Testing" name "...")
    ($let (((trace result) ((wrap $trace-and-result) body env)))
      ($define! error ())
      ($unless (equal? trace expected-trace)
        ($define! error (list* "wrong trace! expected:" expected-trace
                               "but got:" trace
                               error)))
      ($unless (equal? result expected-result)
        ($define! error (list* "wrong result! expected:" expected-result
                               "but got:" result
                               error)))
      ($unless (null? error)
        (apply test-error (list* name error))))))

; Test that evaluation of the given expression signals the given error.
($define! $test-raises
  ($vau (title continuation . body) env
    (println "Testing" title "...")
    ($unless
      (equal? "%%%caught%%%"
              ($let/cc cc
                ($let* ((child
                          (guard-continuation
                            ()
                            cc
                            (list (list (eval continuation env)
                                        ($lambda (tree divert)
                                          (apply divert "%%%caught%%%"))))))
                        (grandchild
                          (extend-continuation
                            child
                            ($lambda #ignore (eval body env)))))
                  (apply-continuation grandchild #inert))))
      (test-error "expected error" continuation "not raised"))))

; Tests BEGIN

; Let's begin by testing trace itself.

($test "trace initial state" () (get-trace))
($test "trace something" ("a") (trace "a") (get-trace))
($test "reset trace" () (reset-trace!) (get-trace))
($test "trace order" ("a" "b")
  (reset-trace!) (trace "a") (trace "b") (get-trace))
($test "$trace-and-result" (("a" "b") "c") ($trace-and-result ((trace "a") (trace "b") "c")))
($t/t "$t/t" ("a" "b") "c" (trace "a") (trace "b") "c")
($test-raises "symbol not found"
  symbol-not-found-continuation
  xyzzywwwwxxxmmm)

; Kernel semantics proper.

($test "param tree matching" ("a" "b" "c" "d" ("e" "f"))
  ($define! (a (b c) d . e)
    (cons "a"
          (cons
            (cons "b" (cons "c" ()))
            (cons "d"
                  (cons "e" (cons "f" ()))))))
  (list a b c d e))

($test "param tree matching in $let" ("a" "b" "c" "d")
  ($let ((a "a")
         ((b c d) (list "b" "c" "d")))
    (list a b c d)))

($test "list, cdddr" ("d" "e") (cdddr (list "a" "b" "c" "d" "e")))

($test "call/cc result" "x"
  ($let/cc cc
    (trace "a")
    (apply (continuation->applicative cc) "x")
    (trace "b")
    "y"))

($t/t "call/cc trace" ("a") "xyz"
  (string-append
    "x"
    ($let/cc cc
        (trace "a")
        (apply-continuation cc "y")
        (trace "b")
        "w")
    "z"))

; I don't think this is Kernel semantics (e.g. read, in 4.10.5, "an applicative
; must have a list of operands", but is this cool or what?
($test "combine with non-list operand" "ha!" (($lambda x x) . "ha!"))
($test "combine with improper list" ("a" . "b") (($lambda x x) "a" . "b"))
($test "combine: final cdr of improper list matches 'rest' formal"
  ("a" "b")
  (($lambda (x . y) (list x y)) "a" . "b"))

($test "simple extend-continuation" "outside inside"
  ($let/cc cc
    (apply-continuation
      (extend-continuation
        cc
        ($lambda x
          (string-append x " inside")))
      "outside")))

($t/t "guard-continuation, no guards"
  ("inner")
  "apply-cont-val inner return"
  ($let/cc cc
    ($let
      ((in-cont
         (extend-continuation
           (guard-continuation
             (list)
             cc
             (list))
           ($lambda x
             (trace "inner")
             (string-append x " inner return")))))
      (apply-continuation in-cont "apply-cont-val"))))

($t/t "non-diverting entry guard"
  ("intercept" "inner")
  "apply-cont-val modified inner return"
  ($let/cc cc
    ($let
      ((in-cont
         (extend-continuation
           (guard-continuation
             (list
               (list
                 cc
                 ($lambda (val divert)
                   (trace "intercept")
                   (string-append val " modified"))))
             cc
             (list))
           ($lambda x
             (trace "inner")
             (string-append x " inner return")))))
      (apply-continuation in-cont "apply-cont-val"))))

($test "$letrec"
  #t
  ($letrec ((f ($lambda (x lst)
                 ($cond
                   ((null? lst) #f)
                   ((equal? x (car lst)) #t)
                   (#t (f x (cdr lst)))))))
    (f "a" (list "C" "b" "a"))))

($t/t "diverting entry guard"
  ("intercept")
  "intercepted! outer"
  (string-append
    ($let/cc cc
      ($let
        ((in-cont
           (extend-continuation
             (guard-continuation
               (list
                 (list
                   cc
                   ($lambda (val divert)
                     (trace "intercept")
                     (apply divert "intercepted!"))))
               cc
               (list))
             ($lambda x
               (trace "inner")
               (string-append x " inner return")))))
        (apply-continuation in-cont "apply-cont-val")))
    " outer"))

($t/t "only one interceptor gets triggered per clause"
  ("first") "whatever"
  ($let/cc cc
    ($let
      ((inner-cont
         (guard-continuation
           (list
             (list (extend-continuation cc ($lambda #ignore #inert))
                   ($lambda (val divert) (trace "doesn't match") val))
             (list cc ($lambda (val divert) (trace "first") val))
             (list cc ($lambda (val divert) (trace "second") val)))
           cc
           ())))
      (apply-continuation inner-cont "whatever"))))

($define! tracing-guard-builder
  ($lambda (root-cont)
    ($lambda (cont name)
      (guard-continuation
        (list (list root-cont
                    ($lambda (x intercept)
                      (trace (string-append "enter " name))
                      x)))
        cont
        (list (list root-cont
                    ($lambda (x intercept)
                      (trace (string-append "exit " name))
                      x)))))))

($define! build-cont-tree
  ($lambda (tree cc)
    ($let ((tracing-guard (tracing-guard-builder cc)))
      ($letrec
        ((aux
           ($lambda (parent-cont node)
             ($cond
               ((symbol? node)
                (tracing-guard parent-cont (symbol->string node)))
               ((pair? node)
                ($let ((new-parent (aux parent-cont (car node))))
                  (list*
                    list
                    new-parent
                    (map1
                      ($lambda (child)
                        (aux new-parent child))
                      (cdr node)))))))))
        (aux cc tree)))))

($define! $with-tracing-guard-tree
  ($vau (tree . body) env
    ($let/cc cc
      (eval (list* $let
                   (list (list tree (build-cont-tree tree cc)))
                   body)
            env))))

; note we'll hit entry guards to 'from'
($define! jump
  ($lambda (from to val-tree)
    (apply-continuation
      (extend-continuation
        from
        ($lambda val-tree
          (apply-continuation to val-tree)))
      val-tree)))

($t/t "simplest tracing guard"
  ("enter child")
  "x"
  ($let/cc cc
    ($let* ((build-tracing-guard (tracing-guard-builder cc))
            (child-cont (build-tracing-guard cc "child")))
      (apply-continuation child-cont "x"))))


($t/t "simple tracing guard"
  ("enter base"
   "enter right"
   "enter right-child"
   "exit right-child"
   "exit right"
   ; note we don't enter or exit `base` anymore
   "enter left"
   "enter left-child")
  "x"
  ($with-tracing-guard-tree
    (base
      (left left-child)
      (right right-child))
    (jump right-child left-child "x")))

($test "simple error handling"
  "caught"
  ($let/cc cc
    ($let* ((child
              (guard-continuation
                ()
                cc
                (list (list error-continuation
                            ($lambda (tree divert)
                              (apply divert "caught"))))))
            (grandchild
              (extend-continuation
                child
                ($lambda #ignore xyzzy))))
      (apply-continuation grandchild "here we go"))))


($test "number parsing and predicate"
  #t
  (number?
    0
    -0
    #b1
    #b#e01
    #e#b-10
    #e#d1
    #e+infinity
    #e-infinity
    #e#b10
    #X1cC
    #xeee
    #x-deadbeef ; negative hex
    999999999999999999999999999999999999999999999999999999999999999 ; decimal bignum
    #xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff ; bignum
    #e#o01234567))

($test "trivial fixnum sum"
  0
  (+))

($test "unary fixnum sum"
  7
  (+ 7))

($test "binary fixnum sum"
  4
  (+ 2 2))

($test "n-ary fixnum sum"
  10
  (+ 2 5 7 -4))

($test "bignum sum"
  999999999999999999999999999999999999999999999999999999999999999
  (+ 444444444444444444444444444444444444444444444444444444444444444
     555555555555555555555555555555555555555555555555555555555555555))

($define! max-fixnum
  ($if (bignum? #x80000000)
    #x7fffffff
    #x7fffffffffffffff))

($define! min-bignum (+ max-fixnum 1))

($test "max fixnum" #t (fixnum? max-fixnum))
($test "max fixnum, promotion" #t (bignum? min-bignum))
($test "demotion to fixnum" #t (fixnum? (+ min-bignum -1)))
($test "+: infinity absorbs fixnum"
  #e+infinity
  (+ 42 #e+infinity))

($test "+: infinity absorbs bignum"
  #e-infinity
  (+ #e-infinity 999999999999999999999999999999999999999999999999999999999999999))

($test "subtraction"
  2
  (- 7 3 2))

($test "order, trivial"
  #t
  (<?))

($test "order, one"
  #t
  (<? 1))

($test "order, several"
  #t
  (<? 2 3 7 9))

($test "equal, one"
  #t
  (=? 2))

($test "equal, several"
  #t
  (=? 4 4 4))

($test "not equal"
  #f
  (=? 4 4 3))

; Encapsulations.

($define! (e1 p1? d1) (make-encapsulation-type))
($define! (e2 p2? d2) (make-encapsulation-type))

($define! w11 (e1 "w11"))
($define! w12 (e1 "w12"))
($define! w2 (e2 "w2"))

($test "trivial encapsulation predicate"
  #t
  (p1?))

($test "unary encapsulation predicate"
  #t
  (p1? w11))

($test "binary encapsulation predicate"
  #t
  (p1? w11 w12))

($test "encapsulation predicate: not an encapsulation"
  #f
  (p1? "not an encapsulation"))

($test "encapsulation predicate: wrong encapsulation type"
  #f
  (p1? w2))

($test "encapsulation predicate: failing on second argument"
  #f
  (p1? w11 w2))

($test "unwrap encapsulation object"
  ("w11" "w2")
  (list (d1 w11) (d2 w2)))

($test-raises "type error on non encapsulation"
  type-error-continuation
  (d1 "not an encapsulation"))

($test-raises "encapsulation type error on the wrong encapsulation"
  encapsulation-type-error-continuation
  (d1 w2))

($test "promise predicate"
  #t
  (promise? ($lazy 1) (memoize 2)))

($test "force non-promise"
  "blah"
  (force "blah"))

($test "force memoization"
  "blah"
  (force (memoize "blah")))

($test "force lazy promise"
  3
  (force ($lazy (+ 1 2))))

($test "promises: first R-1RK test"
  (5 0 10)
  ($define! count 5)
  ($define! p
    ($let ((self (get-current-environment)))
      ($lazy
        ($if (<=? count 0)
          count
          ($sequence
            ($set! self count (- count 1))
            (force p)
            ($set! self count (+ count 2))
            count)))))
  ($let* ((initial-count count)
          (p-result (force p))
          (count-afterwards count))
    (list initial-count p-result count-afterwards)))

($t/t "promises: second R-1RK test"
  ("*")
  #inert
  ($define! p1 ($lazy (trace "*")))
  ($define! p2 ($lazy p1))
  (force p2)
  (force p1))

; Commented out by default because this one takes forever to run.  This is to
; test that chains of forced promises run in constant space.  To convince
; yourself of this fact, uncomment this, and run this side by side with
; a resource monitor.
#;($test "promises: third R-1RK test"
  1000000
  ($define! stream-filter
    ($lambda (p? s)
      ($lazy
        ($let ((v (force s)))
          ($if (null? v)
            v
            ($let ((s (stream-filter p? (cdr v))))
              ($if (p? (car v))
                (cons (car v) s)
                s)))))))
  ($define! from
    ($lambda (n)
      ($lazy (cons n (from (+ n 1))))))
  (car (force (stream-filter ($lambda (n) (=? n 1000000))
                             (from 0)))))

#;($sequence
  (debug-on)
  ($define! x "xx")
  (println (string-append "a" "b"))
  (debug-off))


(println)
(println "All OK.")
