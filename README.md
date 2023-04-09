[非线性薛定谔方程](https://https//en.wikipedia.org/wiki/Nonlinear_Schr%C3%B6dinger_equation)：

$$
\frac{\partial A}{\partial z}=-\frac{\alpha}{2}A-i \frac{\beta_2}{2} \frac{\partial^2 A}{\partial T^2}+i\gamma|A|^2A
$$

显示了光脉冲在通过光纤传播时的包络和相位如何变化，考虑了衰减$\alpha$、群速度色散 $\beta_2$和非线性导致的自相位调制$\gamma$（SPM）。

本文将展示在Python中使用[分步傅里叶法](https://en.wikipedia.org/wiki/Split-step_method)求解非线性薛定谔方程。
